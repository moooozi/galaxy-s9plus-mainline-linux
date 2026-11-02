import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'install_modules', Path(__file__).resolve().parents[1] / 'install-kernel-modules.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ModuleInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.artifact = Path(self.temp.name) / 'artifact'
        (self.root / 'usr/lib').mkdir(parents=True)
        (self.root / 'lib').symlink_to('usr/lib')
        self.artifact.mkdir()
        self.name = 'usr/lib/modules/7.3.9-s9plus/kernel/fs/fuse/fuse.ko'
        self.data = b'test module bytes'
        self.manifest = {'release': '7.3.9-s9plus', 'modules': [
            {'path': self.name, 'sha256': hashlib.sha256(self.data).hexdigest()}]}

    def archive(self, name=None, *, kind=tarfile.REGTYPE, payload=None):
        (self.artifact / 'kernel-manifest.json').write_text(json.dumps(self.manifest))
        with tarfile.open(self.artifact / 'modules.tar.gz', 'w:gz') as archive:
            entry = tarfile.TarInfo(name or self.name)
            entry.type = kind
            content = self.data if payload is None else payload
            if kind == tarfile.REGTYPE:
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            else:
                entry.linkname = '/tmp/outside'
                archive.addfile(entry)
        (self.artifact / 'SHA256SUMS').write_text('')

    def install(self):
        with patch.object(installer.subprocess, 'run'):
            installer.install(self.root, self.artifact)

    def test_regular_usr_module_keeps_lib_symlink(self):
        self.archive()
        self.install()
        self.assertEqual((self.root / self.name).read_bytes(), self.data)
        self.assertEqual((self.root / 'lib').readlink(), Path('usr/lib'))

    def test_traversal_and_top_level_lib_paths_are_rejected(self):
        for name in ['../../outside', 'lib/modules/7.3.9-s9plus/file',
                     'usr/lib/modules/7.3.9-s9plus/../../../../outside']:
            with self.subTest(name=name):
                self.archive(name)
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.install()

    def test_directory_and_symlink_entries_are_rejected(self):
        for kind in (tarfile.DIRTYPE, tarfile.SYMTYPE):
            with self.subTest(kind=kind):
                self.archive(kind=kind)
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.install()

    def test_module_checksum_mismatch_is_rejected(self):
        self.archive(payload=b'corrupted module')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.install()

    def test_unexpected_module_set_is_rejected(self):
        self.archive(self.name + '.extra.ko')
        with self.assertRaisesRegex(ValueError, 'set differs'):
            self.install()


if __name__ == '__main__':
    unittest.main()
