#!/usr/bin/env python3
"""Run under unshare -Urnm: temporary veth pair, separate routing managers, actual SD/UDP/TCP."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from smoke_config import configuration
from test_local import result


def run(*args):
    subprocess.run(args,check=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',required=True)
    p.add_argument('--exe',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--transport',choices=['udp','tcp'],default='udp')
    a=p.parse_args()
    mapping = Path('/proc/self/uid_map').read_text().split()
    if os.geteuid()!=0 or len(mapping)!=3 or mapping[0]!='0' or mapping[1]=='0' or mapping[2]!='1':
        p.error('Run in a new user/mount/network namespace: unshare -Urnm python3 scripts/test_network.py ...')
    sdk,exe,out=Path(a.sdk).resolve(),Path(a.exe).resolve(),Path(a.output).resolve()
    out.mkdir(parents=True,exist_ok=True)
    run('mount','--make-rprivate','/')
    run('mount','-t','tmpfs','tmpfs','/run')
    Path('/run/netns').mkdir()
    run('ip','netns','add','vsk-provider')
    run('ip','netns','add','vsk-consumer')
    run('ip','link','add','vsk-p','type','veth','peer','name','vsk-c')
    for role,dev,addr in [('provider','vsk-p','192.0.2.1'),('consumer','vsk-c','192.0.2.2')]:
        ns='vsk-'+role
        run('ip','link','set',dev,'netns',ns)
        run('ip','netns','exec',ns,'ip','link','set','lo','up')
        run('ip','netns','exec',ns,'ip','addr','add',addr+'/24','dev',dev)
        run('ip','netns','exec',ns,'ip','link','set',dev,'up')
        run('ip','netns','exec',ns,'ip','route','add','224.0.0.0/4','dev',dev)
        config=configuration(role,addr,a.transport)
        config['network']='vsk_net_'+role # distinct local IPC endpoints even with shared /tmp
        (out/(role+'.json')).write_text(json.dumps(config,indent=2)+'\n')
    children=[]; handles=[]
    try:
        for role,seconds in [('provider','12'),('consumer','8')]:
            env=dict(os.environ, VSOMEIP_CONFIGURATION=str(out/(role+'.json')), VSOMEIP_APPLICATION_NAME='vsk_'+role,
                     LD_LIBRARY_PATH=str(sdk/'lib'))
            f=(out/(role+'.log')).open('w'); handles.append(f)
            children.append(subprocess.Popen(['ip','netns','exec','vsk-'+role,str(exe),role,a.transport,seconds,
                                              '4096' if a.transport=='tcp' else '128'],env=env,stdout=f,stderr=subprocess.STDOUT))
            time.sleep(1)
        for child in reversed(children):
            if child.wait(timeout=20): raise RuntimeError('Process failed; inspect logs in '+str(out))
        report={'scope':'Linux isolated veth network', 'transport':a.transport,'consumer':result(out/'consumer.log'),
                'provider':result(out/'provider.log')}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
        for f in handles: f.close()
        for role in ('provider','consumer'): subprocess.run(['ip','netns','delete','vsk-'+role],check=False)


if __name__=='__main__': main()
