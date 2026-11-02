from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class DisplayManagerConfigurationTests(unittest.TestCase):
    def configure(self, root, manager=None):
        for path in ('etc/default', 'etc/ssh/sshd_config.d'):
            (root / path).mkdir(parents=True)
        (root / 'etc/locale.gen').touch()
        script = '''
set -euo pipefail
source "$1/image/common/lib.sh"
R=$2
IMAGE_USER=ubuntu
IMAGE_PASSWORD_HASH=test-only
IMAGE_HOSTNAME=s9plus
IMAGE_LOCALE=en_US.UTF-8
IMAGE_TIMEZONE=Etc/UTC
IMAGE_KEYMAP=us
IMAGE_SSH_KEY=
if [ -n "$3" ]; then
    IMAGE_DISPLAY_MANAGER=$3
    IMAGE_DISPLAY_MANAGER_EXEC=/usr/bin/sddm
fi
in_chroot() { printf '%s\\n' "$*" >> "$R/commands.log"; }
rootfs_configure "$R"
'''
        subprocess.run(['bash', '-c', script, 'test', str(REPO), str(root), manager or ''],
                       check=True, capture_output=True, text=True)

    def test_legacy_default_still_configures_gdm(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.configure(root)
            self.assertIn('AutomaticLogin=ubuntu', (root / 'etc/gdm3/custom.conf').read_text())
            self.assertIn('ssh.socket gdm.service', (root / 'commands.log').read_text())
            self.assertEqual((root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/sbin/gdm3')

    def test_kde_can_configure_sddm_without_a_gdm_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.configure(root, 'sddm.service')
            self.assertFalse((root / 'etc/gdm3/custom.conf').exists())
            self.assertIn('ssh.socket sddm.service', (root / 'commands.log').read_text())
            self.assertEqual((root / 'etc/X11/default-display-manager').read_text().strip(), '/usr/bin/sddm')


if __name__ == '__main__':
    unittest.main()
