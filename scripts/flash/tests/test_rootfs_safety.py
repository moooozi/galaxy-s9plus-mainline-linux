"""Exercise flashing safeguards with mocked ADB; no devices are accessed."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


with patch.dict('os.environ', {'S9PLUS_SERIAL': 'test-only'}):
    spec = importlib.util.spec_from_file_location(
        'flash_rootfs', Path(__file__).resolve().parents[1] / 'flash_s9plus_rootfs_adb.py')
    flash = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flash)


class RootfsSafetyTests(unittest.TestCase):
    def exercise(self, mountinfo='', fsck_status=0):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'rootfs.img'
            image.write_bytes(bytes(flash.MB))
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            calls = []

            def adb(*args, **kwargs):
                calls.append(args)
                command = args[-1]
                replies = {
                    'get-state': 'recovery',
                    'getprop ro.product.device': 'star2lte',
                    'id -u': '0',
                    f'readlink -f {flash.BYNAME}/USERDATA': '/dev/block/sda25',
                    'blockdev --getsize64 /dev/block/sda25': str(flash.MB),
                    'cat /sys/class/block/sda25/dev': '259:9',
                    'cat /proc/self/mountinfo': mountinfo,
                    f'rm -f {flash.REMOTE}; sync': '',
                }
                if command in replies:
                    return replies[command]
                if command.startswith('dd if=/dev/block/sda25 ') and command.endswith('| sha256sum'):
                    return digest + '  -'
                self.fail('Unexpected or mutating ADB command: ' + repr(args))

            result = SimpleNamespace(returncode=fsck_status, stdout='', stderr='')
            with patch.object(flash, 'adb', side_effect=adb), \
                 patch.object(flash.subprocess, 'run', return_value=result) as run, \
                 patch.object(flash.sys, 'argv', ['flash', str(image)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                try:
                    status = flash.main()
                finally:
                    self.assertFalse(any(call[0] == 'push' for call in calls))
                self.assertIn('rc=$?; blkid /dev/block/sda25; exit $rc', run.call_args.args[0][-1])
                return status

    def test_mounted_aliases_and_bind_mounts_are_rejected(self):
        for root, mountpoint in [('/', '/data'), ('/media', '/sdcard')]:
            with self.subTest(root=root):
                mountinfo = (f'42 1 259:9 {root} {mountpoint} rw - ext4 '
                             f'{flash.BYNAME}/USERDATA rw\n')
                with self.assertRaisesRegex(SystemExit, 'is mounted'):
                    self.exercise(mountinfo=mountinfo)

    def test_unrelated_mount_is_allowed(self):
        self.assertEqual(self.exercise(mountinfo='42 1 259:8 / /other rw - ext4 /dev/block/sda24 rw'), 0)

    def test_fsck_success_and_repair_statuses_are_allowed(self):
        for status in (0, 1, 2, 3):
            with self.subTest(status=status):
                self.assertEqual(self.exercise(fsck_status=status), 0)

    def test_fsck_failures_stop_the_flash_helper(self):
        for status in (4, 8, 16, 32, 128, 255):
            with self.subTest(status=status):
                with self.assertRaisesRegex(SystemExit, 'Filesystem check failed'):
                    self.exercise(fsck_status=status)


if __name__ == '__main__':
    unittest.main()
