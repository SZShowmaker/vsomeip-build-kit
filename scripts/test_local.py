#!/usr/bin/env python3
"""Bounded two-process smoke; same-host IPC, NOT proof of UDP/TCP on the wire."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from smoke_config import configuration


def result(path):
    lines = path.read_text(errors='replace').splitlines()
    values = [json.loads(line[7:]) for line in lines if line.startswith('RESULT ')]
    if len(values) != 1:
        raise RuntimeError('Missing single RESULT: ' + str(path))
    value = values[0]
    if value['errors'] or (value['role'] == 'consumer' and (value['responses'] < 10 or value['events'] < 10)):
        raise RuntimeError('Invalid result: ' + str(value))
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk', required=True)
    p.add_argument('--exe', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--transport', choices=['udp','tcp'], default='udp')
    p.add_argument('--restart', action='store_true', help='Keep consumer alive across provider restart')
    a = p.parse_args()
    sdk, exe, out = Path(a.sdk).resolve(), Path(a.exe).resolve(), Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / 'local.json'
    cfg.write_text(json.dumps(configuration('provider', '127.0.0.1', a.transport, True), indent=2))
    base = dict(os.environ, VSOMEIP_CONFIGURATION=str(cfg))
    var = 'PATH' if os.name == 'nt' else 'LD_LIBRARY_PATH'
    base[var] = str(sdk / ('bin' if os.name == 'nt' else 'lib')) + os.pathsep + base.get(var, '')
    processes, handles = [], []
    def start(role, seconds, label):
        log = out / (label + '.log')
        f = log.open('w'); handles.append(f)
        env = dict(base, VSOMEIP_APPLICATION_NAME='vsk_' + role)
        proc = subprocess.Popen([str(exe), role, a.transport, str(seconds), '128'], env=env, stdout=f, stderr=subprocess.STDOUT)
        processes.append(proc)
        return proc, log
    try:
        provider, provider_log = start('provider', 6 if a.restart else 12, 'provider')
        time.sleep(1)
        consumer, consumer_log = start('consumer', 18 if a.restart else 8, 'consumer')
        if a.restart:
            if provider.wait(timeout=12): raise RuntimeError('First provider failed')
            time.sleep(2)
            provider, provider_log = start('provider', 12, 'provider-restarted')
        if consumer.wait(timeout=25): raise RuntimeError('Consumer failed: ' + str(consumer_log))
        if provider.wait(timeout=20): raise RuntimeError('Provider failed: ' + str(provider_log))
        r = result(consumer_log)
        if a.restart and (r['discoveries'] < 2 or r['losses'] < 1):
            raise RuntimeError('No service recovery observed: ' + str(r))
        report = {'scope':'same-host IPC', 'restart':a.restart, 'consumer':r, 'provider':result(provider_log)}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        for f in handles: f.close()


if __name__ == '__main__':
    main()
