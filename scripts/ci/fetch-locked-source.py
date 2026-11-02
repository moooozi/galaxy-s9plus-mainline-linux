#!/usr/bin/env python3
"""Fetch a reviewed commit and export source with Unix text line endings."""
import argparse
import re
import shutil
import subprocess
from pathlib import Path


def export(url, commit, destination):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('A full source commit is required')
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    # Separate checkout avoids submodule empty directories in the export.
    checkout = destination.with_name(destination.name + '.git-source')
    if checkout.exists():
        raise FileExistsError(checkout)
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'init', str(checkout)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth=1', url, commit], check=True)
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'FETCH_HEAD'], text=True).strip()
    if actual != commit:
        raise ValueError(f'Wrong source commit: {actual}')
    destination.mkdir(parents=True)
    with subprocess.Popen(['git', '-C', str(checkout), 'archive', actual], stdout=subprocess.PIPE) as archive:
        subprocess.run(['tar', '-x', '-C', str(destination)], stdin=archive.stdout, check=True)
        if archive.wait():
            raise RuntimeError('git archive failed')
    for path in destination.rglob('*'):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if b'\r\n' in data and b'\0' not in data:
                path.write_bytes(data.replace(b'\r\n', b'\n'))
    shutil.rmtree(checkout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('commit')
    parser.add_argument('destination')
    args = parser.parse_args()
    export(args.url, args.commit, args.destination)
