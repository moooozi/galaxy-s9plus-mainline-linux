#!/usr/bin/env python3
"""Package three sensor modules and guarded services for a built-in-idle kernel."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[2]


def main():
    work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / '.build/sensors-idle'
    source = Path(os.environ.get('KERNEL_SRC', str(work / 'src')))
    out = source / 'out'
    release = (out / 'include/config/kernel.release').read_text().strip()
    if 'CONFIG_S9PLUS_CPUIDLE=y' not in (out / '.config').read_text().splitlines():
        raise ValueError('Trial services require the integrated CPU-idle kernel')
    if 'kernel/drivers/cpuidle/s9plus-cpuidle.ko' not in (out / 'modules.builtin').read_text().splitlines():
        raise ValueError('CPU idle was not linked into the kernel')
    files = {}
    files['usr/local/lib/s9plus-sensors/compat/libwakelock-no-suspend.so'] = \
        work / 'compat/libwakelock-no-suspend.so'
    for name, kind in [('industrialio.ko', 'sensors'), ('zrn-bbd.ko', 'sensors'),
                       ('s9plus-sensor-iio.ko', 'sensors')]:
        source = work / 'modules' / name
        vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(source)], text=True)
        if not vermagic.startswith(release + ' '):
            raise ValueError(f'Wrong ABI: {source}')
        files[f'usr/lib/modules/{release}/extra/s9plus-{kind}/{name}'] = source
    for kind in ('sensors', 'cpuidle'):
        root = REPO / 'experiments' / kind / 'rootfs'
        for source in root.rglob('*'):
            if '__pycache__' in source.parts or source.suffix == '.pyc':
                continue
            if source.is_symlink():
                raise ValueError(f'Unexpected trial overlay symlink: {source}')
            if source.is_file():
                name = str(source.relative_to(root))
                if name in files:
                    raise ValueError(f'Duplicate destination: {name}')
                files[name] = source
    manifest = {'release': release,
                'upstream_commit': '7f42ddc3ba468e4e21c7145cbb973f5aa57d5358',
                'phone_tested': False, 'services_enabled': False, 'files': []}
    with tarfile.open(work / 'install.tar.gz', 'w:gz') as archive:
        for name, source in sorted(files.items()):
            info = archive.gettarinfo(str(source), name)
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            with source.open('rb') as stream:
                archive.addfile(info, stream)
            manifest['files'].append({'path': name,
                'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    (work / 'install-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (work / 'install.SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256((work / name).read_bytes()).hexdigest()}  {name}\n'
        for name in ('install.tar.gz', 'install-manifest.json')))
    print(f'{work / "install.tar.gz"}: {len(files)} regular files, {release}, not phone-tested')


if __name__ == '__main__':
    main()
