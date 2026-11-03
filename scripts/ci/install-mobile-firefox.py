#!/usr/bin/env python3
"""Build a pinned mobile Firefox configuration DEB for both phone desktops."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def build(output, source=None):
    lock_path = REPO / 'image/mobile/firefox-source.json'
    lock = json.loads(lock_path.read_text())
    with tempfile.TemporaryDirectory(prefix='s9plus-firefox-') as temporary:
        work = Path(temporary)
        if source is None:
            spec = importlib.util.spec_from_file_location('fetch', REPO / 'scripts/ci/fetch-locked-source.py')
            fetch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fetch)
            source = work / 'source'
            fetch.export(lock['url'], lock['commit'], source)
        else:
            source = Path(source).resolve()
            actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != lock['commit']:
                raise ValueError('Firefox configuration source does not match lock')
            if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']):
                raise ValueError('Firefox configuration source has local changes')
        root = work / 'package'
        firefox = root / 'usr/lib/firefox'
        defaults = firefox / 'defaults/pref'
        defaults.mkdir(parents=True)
        for name, destination in (
            ('mobile-config-prefs.js', defaults),
            ('mobile-config-autoconfig.js', firefox),
        ):
            shutil.copyfile(source / 'src' / name, destination / name)
        runtime = root / 'usr/lib/mobile-config-firefox'
        shutil.copytree(source / 'src/modules', runtime)
        shutil.copytree(source / 'src/themes', runtime / 'themes')
        # Install the mobile UI only. Keep search engines, bookmarks, extensions
        # and existing enterprise policies under the user's control.
        doc = root / 'usr/share/doc/s9plus-mobile-firefox'
        doc.mkdir(parents=True)
        shutil.copyfile(source / 'LICENSE', doc / 'copyright')
        shutil.copyfile(lock_path, doc / 'source.json')
        control = root / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text(
            'Package: s9plus-mobile-firefox\nVersion: 1.0+' + lock['commit'][:12] + '\n'
            'Architecture: all\nDepends: firefox\nSection: web\nPriority: optional\n'
            'Maintainer: Galaxy S9+ Linux contributors\n'
            'Description: Mobile Firefox layout and touch defaults for Galaxy S9+\n'
            ' Pinned postmarketOS mobile-config-firefox runtime, without enterprise policies.\n')
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(root), str(output)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    build(args.output, args.source)
