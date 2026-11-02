#!/usr/bin/env python3
"""Resolve the newest supported patch in the configured kernel series.

Emit a per-build source manifest. Consumers must use its resolved tag/commit
throughout the build, rather than querying again in individual jobs.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import urllib.request


def select_release(policy, metadata):
    if policy['policy'] != 'latest-supported-patch':
        raise ValueError('Unsupported kernel selection policy')
    series = policy['series']
    if not re.fullmatch(r'[0-9]+\.[0-9]+', series):
        raise ValueError('Kernel series must have major.minor only')
    candidates = []
    for release in metadata['releases']:
        version = release.get('version', '')
        if not re.fullmatch(re.escape(series) + r'(?:\.[0-9]+)?', version):
            continue
        if release.get('iseol') is not False:
            continue
        if release.get('moniker') not in ('stable', 'longterm', 'mainline'):
            continue
        candidates.append(version)
    if not candidates:
        raise ValueError(f'No supported {series}.x release; review the kernel series')
    return max(candidates, key=lambda version: tuple(map(int, version.split('.'))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path,
                        default=Path(__file__).with_name('kernel-source.json'))
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    with urllib.request.urlopen(policy['releases_url'], timeout=60) as response:
        metadata = json.load(response)
    version = select_release(policy, metadata)
    tag = f'v{version}'
    refs = subprocess.check_output(
        ['git', 'ls-remote', '--tags', policy['url'], f'refs/tags/{tag}',
         f'refs/tags/{tag}^{{}}'], text=True, timeout=60)
    refs = dict(line.split()[::-1] for line in refs.splitlines())
    commit = refs.get(f'refs/tags/{tag}^{{}}', refs.get(f'refs/tags/{tag}', ''))
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError(f'Could not resolve exact source commit for {tag}')
    print(json.dumps({**policy, 'version': version, 'tag': tag, 'commit': commit}, indent=2))


if __name__ == '__main__':
    main()
