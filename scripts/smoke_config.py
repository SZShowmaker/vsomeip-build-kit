#!/usr/bin/env python3
"""Create explicit isolated vSomeIP smoke configurations (no system config changes)."""
import argparse
import ipaddress
import json
from pathlib import Path


def configuration(role, address, transport, local=False):
    ipaddress.IPv4Address(address)
    service = {'service':'0x6b10','instance':'0x0001',
               'reliable' if transport == 'tcp' else 'unreliable': '30511',
               'events':[{'event':'0x8001','is_field':'false','is_reliable':str(transport == 'tcp').lower()}],
               'eventgroups':[{'eventgroup':'0x0001','events':['0x8001']}]}
    data = {'unicast':address, 'network':'vsk_smoke',
            'logging':{'level':'warning','console':'true','dlt':'false'},
            'applications':[{'name':'vsk_provider','id':'0x6b01'}, {'name':'vsk_consumer','id':'0x6b02'}],
            'routing':'vsk_provider' if local or role == 'provider' else 'vsk_consumer',
            'service-discovery':{'enable':'true','multicast':'224.244.224.245','port':'30510','protocol':'udp',
                                 'initial_delay_min':'10','initial_delay_max':'100','repetitions_base_delay':'200',
                                 'repetitions_max':'3','ttl':'3','cyclic_offer_delay':'1000','request_response_delay':'10'}}
    if role == 'provider' or local:
        data['services'] = [service]
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role', choices=['provider','consumer'], required=True)
    p.add_argument('--address', required=True, help='Local IPv4 address, not peer address')
    p.add_argument('--transport', choices=['udp','tcp'], default='udp')
    p.add_argument('--local', action='store_true', help='Two processes on one host share provider routing manager')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    dest = Path(a.output); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(configuration(a.role, a.address, a.transport, a.local), indent=2)+'\n')
    print(dest)


if __name__ == '__main__':
    main()
