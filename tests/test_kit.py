import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from kit import extract, apply_patches, digest, LOCK
from verify_sdk import verify
from smoke_config import configuration

class ArchiveTests(unittest.TestCase):
    def test_reject_escape_and_links(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('root/link', tarfile.SYMTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                archive=Path(td)/'bad.tar'
                with tarfile.open(archive, 'w') as tf:
                    info=tarfile.TarInfo(name); info.type=kind
                    if kind == tarfile.SYMTYPE: info.linkname='/tmp'
                    tf.addfile(info, io.BytesIO(b''))
                with self.assertRaises(RuntimeError): extract(archive,Path(td)/'source')
                self.assertFalse((Path(td)/'source').exists())

    def test_remote_consumer_does_not_offer_service(self):
        c=configuration('consumer','192.0.2.2','tcp')
        self.assertNotIn('services',c)
        self.assertEqual(c['routing'],'vsk_consumer')
        with self.assertRaises(ValueError): configuration('provider','not-an-ip','udp')

class IntegrityTests(unittest.TestCase):
    def test_patch_refuses_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'CMakeLists.txt').write_text('unexpected upstream text')
            with self.assertRaisesRegex(RuntimeError,'preimage mismatch'):
                apply_patches(root)
            self.assertEqual((root/'CMakeLists.txt').read_text(),'unexpected upstream text')

    def test_sdk_detects_corruption_and_extra_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'sources.lock.json').write_text(json.dumps(LOCK))
            (root/'library').write_bytes(b'expected')
            manifest={p.name:digest(p) for p in root.iterdir()}
            (root/'manifest.sha256.json').write_text(json.dumps(manifest))
            verify(root)
            (root/'library').write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError,'checksum'): verify(root)
            (root/'library').write_bytes(b'expected')
            (root/'unexpected').write_text('local change')
            with self.assertRaisesRegex(RuntimeError,'file set'): verify(root)

if __name__=='__main__': unittest.main()
