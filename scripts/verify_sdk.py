#!/usr/bin/env python3
"""Check all SDK file hashes, manifest completeness, and source versions."""
import argparse
import json
from pathlib import Path
from kit import digest, LOCK


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root/'manifest.sha256.json').read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='manifest.sha256.json'}
    if set(manifest)!=actual:
        raise RuntimeError('SDK file set differs: '+str(set(manifest)^actual))
    for name, sha in manifest.items():
        path=root/name
        if not path.resolve().is_relative_to(root) or digest(path)!=sha:
            raise RuntimeError('SDK checksum/path mismatch: '+name)
    if json.loads((root/'sources.lock.json').read_text()) != LOCK:
        raise RuntimeError('SDK does not match this repository source lock')
    print('verified',len(manifest),'SDK files:',root)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',required=True)
    verify(p.parse_args().sdk)
