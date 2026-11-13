#!/usr/bin/env python3
"""Reject mismatched image/kernel bundles and shared first-boot identities."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
variant = sys.argv[2]
flavor = 'unified'
manifest = json.loads((root / f'usr/share/s9plus-kernel/{flavor}/kernel-manifest.json').read_text())
if manifest['variant'] != flavor or manifest['release'] != manifest['version'] + '-s9plus':
    raise ValueError('image/kernel variant mismatch')
boot = root / f'usr/share/s9plus-kernel/{flavor}/boot-s9plus.img'
if hashlib.file_digest(boot.open('rb'), 'sha256').hexdigest() != manifest['boot_sha256']:
    raise ValueError('BOOT checksum mismatch')
for item in manifest['modules']:
    path = root / item['path']
    if not path.exists() and item['path'].startswith('usr/lib/modules/'):
        path = root / item['path'][4:]
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
            raise ValueError('module checksum mismatch: ' + item['path'])
if list((root / 'etc/ssh').glob('ssh_host_*')):
    raise ValueError('SSH host keys must be generated per device')
if (root / 'etc/machine-id').read_text().strip():
    raise ValueError('machine-id must be generated per device')
if (root / 'var/lib/s9plus/first-boot-complete').exists():
    raise ValueError('first boot already ran in build environment')
subprocess.run(['chroot', str(root), 'test', '-x', '/sbin/init'], check=True)
subprocess.run(['chroot', str(root), 'test', '-x', '/usr/local/sbin/s9plus-first-boot'], check=True)
for name in ('s9plus-first-boot.service','s9plus-cpuidle.service','usb-gadget.service','s9plus-battery-settings.service'):
    path = root / 'etc/systemd/system/multi-user.target.wants' / name
    if not path.is_symlink():
        raise ValueError('required service not enabled: ' + name)
desktop = variant != 'debian-headless'
expected = {'start': 98, 'stop': 100} if desktop else {'start': 63, 'stop': 65}
if json.loads((root / 'etc/s9plus/battery-preservation.json').read_text()) != expected:
    raise ValueError('incorrect image charging defaults')
if not desktop:
    for name in ('s9plus-audio', 's9plus-bluetooth', 's9plus-sensorhub', 's9plus-sensors'):
        path = root / f'etc/systemd/system/{name}.service'
        if not path.is_symlink() or path.readlink() != Path('/dev/null'):
            raise ValueError('headless hardware helper must remain masked: ' + name)
    packages = subprocess.check_output(['chroot', str(root), 'dpkg-query', '-W', '-f=${binary:Package}\n'], text=True).splitlines()
    forbidden = ('gnome-shell','plasma-mobile','phosh','gdm3','sddm','bluez','pipewire')
    if set(packages).intersection(forbidden):
        raise ValueError('headless image contains a desktop/audio/Bluetooth stack')
else:
    (root / 'etc/apk/repositories').read_text().index('https://moooozi.github.io/galaxy-s9plus-kernel/apk')
print('Validated ' + variant + ' with ' + manifest['release'])
