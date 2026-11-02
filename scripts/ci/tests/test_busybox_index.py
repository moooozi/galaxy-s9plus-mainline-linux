import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'fetch_busybox', Path(__file__).resolve().parents[2] / 'build/fetch_busybox.py')
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class BusyboxIndexTests(unittest.TestCase):
    def test_authenticated_hash_and_size_must_both_match(self):
        data = b'compressed package index'
        path = 'main/binary-arm64/Packages.gz'
        release = f'SHA256:\n {hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'
        fetcher.verify_index(release, data, path)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            fetcher.verify_index(release, b'X' * len(data), path)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            fetcher.verify_index(release, data + b'X', path)

    def test_missing_hash_cannot_fall_back_to_unsigned_index(self):
        with self.assertRaisesRegex(ValueError, 'no SHA256'):
            fetcher.verify_index('SHA256:\n abc 1 other-file\n', b'x', 'Packages.gz')
