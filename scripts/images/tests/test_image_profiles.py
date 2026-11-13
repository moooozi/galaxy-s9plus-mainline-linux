"""Exercise image policy independently of a kernel build or attached phone."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('configure_rootfs', REPO / 'scripts/images/configure-rootfs.py')
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


class ImageProfiles(unittest.TestCase):
    def test_common_kernel_has_distinct_image_policies(self):
        for variant in ('debian-headless', 'postmarketos-plasma', 'postmarketos-phosh'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'sbin').mkdir()
                (root / 'etc/ssh').mkdir(parents=True)
                (root / 'etc/ssh/ssh_host_ed25519_key').write_text('must be removed')
                with patch.object(sys, 'argv', ['configure', str(root), variant]), patch.object(configure.subprocess, 'run') as run:
                    configure.main()
                desktop = variant != 'debian-headless'
                self.assertEqual(json.loads((root / 'etc/s9plus/battery-preservation.json').read_text()),
                                 {'start': 98, 'stop': 100} if desktop else {'start': 63, 'stop': 65})
                commands = [call.args[0] for call in run.call_args_list]
                enabled = [name for cmd in commands if 'enable' in cmd for name in cmd[cmd.index('enable') + 1:]]
                self.assertIn('s9plus-battery-settings.service', enabled)
                self.assertIn('graphical.target' if desktop else 'multi-user.target', commands[0])
                for name in ('s9plus-audio', 's9plus-bluetooth', 's9plus-sensors'):
                    self.assertEqual(name + '.service' in enabled, desktop)
                if not desktop:
                    for name in ('s9plus-audio', 's9plus-bluetooth', 's9plus-sensorhub', 's9plus-sensors'):
                        self.assertEqual((root / f'etc/systemd/system/{name}.service').readlink(), Path('/dev/null'))
                self.assertEqual((root / 'etc/systemd/system/suspend.target').readlink(), Path('/dev/null'))
                self.assertFalse(list((root / 'etc/ssh').glob('ssh_host_*')))
                self.assertEqual((root / 'etc/machine-id').read_text(), '')
