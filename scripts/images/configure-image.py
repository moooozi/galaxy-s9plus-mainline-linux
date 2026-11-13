#!/usr/bin/env python3
"""Preconfigure an uncompressed ext4 image without mounting it.

Example: configure-image.py s9plus-rootfs.img --user alice --ssh-public-key ~/.ssh/id_ed25519.pub
Only a public key and optional password hash are written into the image.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader('firstboot', str(REPO / 'image/debian/rootfs/usr/local/sbin/s9plus-first-boot'))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--user', default='debian')
    parser.add_argument('--ssh-public-key', type=Path, action='append', default=[])
    parser.add_argument('--password-file', type=Path, help='optional private file containing the desired password')
    args = parser.parse_args()
    image = args.image.resolve(strict=True)
    if not image.is_file() or image.is_symlink() or image.suffix != '.img':
        raise ValueError('expected a regular, uncompressed .img file')
    # e2fsck refuses mounted filesystems. Require a clean image before editing.
    subprocess.run(['e2fsck', '-fn', str(image)], check=True, stdout=subprocess.DEVNULL)
    config = {'user': args.user, 'ssh_authorized_keys': [key.read_text().strip() for key in args.ssh_public_key]}
    if args.password_file:
        password = args.password_file.read_text().rstrip('\n')
        if not password or any(c in password for c in '\r\n:'):
            raise ValueError('invalid password file')
        config['password_hash'] = subprocess.check_output(['openssl', 'passwd', '-6', '-stdin'], input=password+'\n', text=True).strip()
    module.validate(config)
    with tempfile.TemporaryDirectory(prefix='s9plus-config-') as directory:
        source = Path(directory) / 'first-boot.json'
        source.write_text(json.dumps(config) + '\n')
        source.chmod(0o600)
        commands = Path(directory) / 'commands'
        commands.write_text('mkdir /etc/s9plus\nrm /etc/s9plus/first-boot.json\nwrite ' + str(source) + ' /etc/s9plus/first-boot.json\nset_inode_field /etc/s9plus/first-boot.json mode 0100600\n')
        subprocess.run(['debugfs', '-w', '-f', str(commands), str(image)], check=True)
        # debugfs can exit zero on command errors; verify the exact payload.
        found = subprocess.check_output(['debugfs', '-R', 'cat /etc/s9plus/first-boot.json', str(image)], text=True)
        if json.loads(found) != config:
            raise RuntimeError('image account configuration readback failed')
    subprocess.run(['e2fsck', '-fn', str(image)], check=True, stdout=subprocess.DEVNULL)
    print('Configured user ' + args.user + (' with SSH key login' if args.ssh_public_key else ' with password login'))


if __name__ == '__main__':
    main()
