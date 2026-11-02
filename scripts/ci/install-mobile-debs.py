#!/usr/bin/env python3
"""Install the exact runtime subset of the separately built GNOME Mobile .debs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]


def main():
    root, artifact = map(lambda p: Path(p).resolve(), sys.argv[1:])
    lock = json.loads((REPO / 'image/gnome-mobile/sources.json').read_text())
    if json.loads((artifact / 'sources.json').read_text()) != lock:
        raise ValueError('GNOME artifact does not match the reviewed source lock')
    subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=artifact, check=True)
    required = (REPO / 'image/gnome-mobile/runtime-packages.txt').read_text().split()
    selected = {}
    for deb in sorted(artifact.glob('*.deb')):
        fields = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Package', 'Version', 'Architecture'], text=True)
        values = dict(line.split(': ', 1) for line in fields.splitlines())
        if values['Package'] not in required:
            continue
        if values['Version'] != lock['debian_version'] or values['Architecture'] not in ('all', 'arm64'):
            raise ValueError(f'Wrong package version or architecture: {deb}')
        if values['Package'] in selected:
            raise ValueError(f'Duplicate package: {values["Package"]}')
        selected[values['Package']] = deb
    if set(selected) != set(required):
        raise ValueError('Missing runtime packages: ' + repr(set(required) - set(selected)))
    staged = root / 'var/tmp/s9plus-mobile-debs'
    staged.mkdir()
    for path in selected.values():
        shutil.copyfile(path, staged / path.name)
    subprocess.run(['chroot', str(root), 'apt-get', '-y', '--no-install-recommends', 'install',
                    *['/var/tmp/s9plus-mobile-debs/' + path.name for path in selected.values()]], check=True)
    versions = subprocess.check_output(['chroot', str(root), 'dpkg-query', '-W',
                                       '-f=${Package} ${Version}\n', *required], text=True)
    for line in versions.splitlines():
        if line.split()[1] != lock['debian_version']:
            raise ValueError('Stock GNOME package remained installed: ' + line)
    # Keep all three components on the same reviewed version until rebuilt.
    subprocess.run(['chroot', str(root), 'apt-mark', 'hold', *required], check=True)
    shutil.rmtree(staged)


if __name__ == '__main__':
    main()
