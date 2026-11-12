#!/usr/bin/env python3
"""Install only the regular usr/lib module files matching the BOOT manifest."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def install(root, artifact):
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=artifact, check=True)
    manifest = json.loads((artifact / 'kernel-manifest.json').read_text())
    compat = artifact / 'libwakelock-no-suspend.so'
    if hashlib.sha256(compat.read_bytes()).hexdigest() != manifest['sensor_compat_sha256']:
        raise ValueError('Sensor compatibility library checksum mismatch')
    destination = root / 'usr/local/lib/s9plus-sensors/compat/libwakelock-no-suspend.so'
    if not destination.resolve().is_relative_to(root) or destination.is_symlink():
        raise ValueError('Sensor compatibility destination escapes rootfs')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(compat, destination)
    destination.chmod(0o644)
    release = manifest['release']
    if '/' in release or release in ('.', '..'):
        raise ValueError('Invalid kernel release')
    if (root / 'lib').readlink() != Path('usr/lib'):
        raise ValueError('Rootfs must retain /lib -> usr/lib')
    prefix = f'usr/lib/modules/{release}/'
    seen = set()
    with tarfile.open(artifact / 'modules.tar.gz') as archive:
        for member in archive:
            path = Path(member.name)
            if not member.isreg() or not member.name.startswith(prefix) or '..' in path.parts:
                raise ValueError(f'Unsafe module archive member: {member.name}')
            if member.name in seen:
                raise ValueError(f'Duplicate module archive member: {member.name}')
            seen.add(member.name)
            target = root / path
            if not target.resolve().is_relative_to(root) or target.is_symlink():
                raise ValueError(f'Module destination escapes rootfs: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('wb') as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o644)
    expected = {entry['path'] for entry in manifest['modules']}
    if {name for name in seen if name.endswith('.ko')} != expected:
        raise ValueError('Module set differs from manifest')
    for entry in manifest['modules']:
        with (root / entry['path']).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != entry['sha256']:
                raise ValueError(f'Module checksum mismatch: {entry["path"]}')
    subprocess.run(['chroot', str(root), 'depmod', '-a', release], check=True)
    for module in ('fuse', 'snd-zrn-abox', 'hci_uart', 'zrn-bt', 'industrialio',
                   'zrn-bbd', 's9plus-sensor-iio', 's9plus-cpuidle'):
        subprocess.run(['chroot', str(root), 'modprobe', '--set-version', release,
                        '--show-depends', module], check=True)


if __name__ == '__main__':
    install(*sys.argv[1:])
