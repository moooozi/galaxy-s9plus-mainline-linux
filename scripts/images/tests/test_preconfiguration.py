"""Exercise offline image configuration without mounting a filesystem."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class ImagePreconfiguration(unittest.TestCase):
    def test_public_key_roundtrip_and_invalid_user_do_not_corrupt_image(self):
        with tempfile.TemporaryDirectory(prefix='s9plus-image-check-') as directory:
            base = Path(directory)
            tree = base / 'tree'
            (tree / 'etc').mkdir(parents=True)
            image = base / 'rootfs.img'
            subprocess.run(['mke2fs','-q','-F','-t','ext4','-d',str(tree),str(image),'32M'], check=True, capture_output=True)
            key = base / 'id_ed25519'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)], check=True)
            command = ['python3',str(REPO/'scripts/images/configure-image.py'),str(image),
                       '--user','alice','--ssh-public-key',str(key)+'.pub']
            subprocess.run(command, check=True, capture_output=True)
            output = subprocess.check_output(['debugfs','-R','cat /etc/s9plus/first-boot.json',str(image)], stderr=subprocess.DEVNULL)
            config = json.loads(output)
            self.assertEqual(config['user'],'alice')
            self.assertEqual(config['ssh_authorized_keys'],[Path(str(key)+'.pub').read_text().strip()])
            self.assertNotIn('password_hash',config)
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            command[command.index('alice')] = 'root'
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(),before)

    def test_networkmanager_profile_is_private_after_git_style_checkout(self):
        spec = importlib.util.spec_from_file_location('rootfs_configuration',REPO/'scripts/images/configure-rootfs.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base/'usb0.nmconnection'
            source.write_text('[connection]\nid=test\n')
            source.chmod(0o644)  # Git stores regular files as 0644 or 0755.
            root = base/'root'
            target = 'etc/NetworkManager/system-connections/usb0.nmconnection'
            module.install_file(root,source,target)
            self.assertEqual((root/target).stat().st_mode & 0o777,0o600)
