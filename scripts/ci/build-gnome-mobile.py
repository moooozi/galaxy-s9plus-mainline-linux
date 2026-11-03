#!/usr/bin/env python3
"""Build the locked GNOME Mobile stack using Ubuntu's Debian packaging.

Run as root in an ephemeral native ARM64 Ubuntu 26.10 container. No raw
`meson install` is used on the image: dpkg owns the resulting stack.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts/ci'))
from importlib import import_module
export = import_module('fetch-locked-source').export


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def mobile_mutter_symbols(source):
    # This is a different, version-coupled ABI from Ubuntu's desktop Mutter.
    # Remove only reviewed differences; dpkg still rejects any other loss.
    removals = json.loads((REPO / 'image/gnome-mobile/mutter-symbol-removals.json').read_text())
    symbols = source / 'debian/libmutter-51-0.symbols'
    text = symbols.read_text()
    for declaration in removals:
        line = ' ' + declaration + '\n'
        if text.count(line) != 1:
            raise ValueError(f'Mutter symbol baseline changed: {declaration}')
        text = text.replace(line, '')
    symbols.write_text(text)


def mobile_shell_dependencies(source):
    # Mobile imports these namespaces unconditionally. Desktop Ubuntu's
    # packaging only declares the Autoar shared library, not its GI typelib.
    control = source / 'debian/control'
    text = control.read_text()
    additions = {
        '         gir1.2-gnomedesktop-4.0 (>= 40),\n': '         gir1.2-gnomeautoar-0.1,\n',
        '         gir1.2-mutter-51 (>= 51),\n': '         gir1.2-modemmanager-1.0,\n',
    }
    for anchor, dependency in additions.items():
        if text.count(anchor) != 1 or dependency in text:
            raise ValueError('Shell dependency baseline changed; review mobile imports')
        text = text.replace(anchor, dependency + anchor)
    control.write_text(text)


def prepare(lock, work):
    sources = {}
    for component in lock['components']:
        name = component['name']
        path = work / name
        export(component['url'], component['commit'], path)
        if f"version: '{lock['version']}'" not in (path / 'meson.build').read_text():
            raise ValueError(f'{name}: source version does not match the stack lock')
        sources[name] = path
    for subproject in lock['subprojects']:
        path = sources[subproject['parent']] / subproject['path']
        # git archive emits empty directories for Git submodules.
        if path.exists():
            path.rmdir()
        export(subproject['url'], subproject['commit'], path)
    return sources


def main():
    lockpath = REPO / 'image/gnome-mobile/sources.json'
    lock = json.loads(lockpath.read_text())
    expected_arch = os.environ.get('GNOME_BUILD_ARCH', 'arm64')
    if expected_arch not in ('arm64', 'amd64'):
        raise SystemExit('Unsupported native build architecture')
    if os.geteuid() or subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() != expected_arch:
        raise SystemExit(f'Run as root in a native {expected_arch} Ubuntu 26.10 container')
    if 'VERSION_ID="26.10"' not in Path('/etc/os-release').read_text():
        raise SystemExit('The GNOME packages must use the target Ubuntu 26.10 userspace')
    work = Path(os.environ.get('GNOME_WORK', '/build/gnome-mobile'))
    out = Path(os.environ.get('GNOME_OUT', str(REPO / 'dist/gnome-mobile-packages')))
    if work.exists():
        raise SystemExit(f'{work} already exists; use a fresh build directory')
    work.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit(f'Output must be empty: {out}')
    os.environ.update(DEBIAN_FRONTEND='noninteractive', DEB_BUILD_OPTIONS='nocheck parallel=' + os.environ.get('BUILD_JOBS', '4'),
                      DPKG_GENSYMBOLS_CHECK_LEVEL='1')
    # Keep apt-secure verification for binary packages and source metadata.
    mirror = ('http://ports.ubuntu.com/ubuntu-ports' if expected_arch == 'arm64'
              else 'http://archive.ubuntu.com/ubuntu')
    Path('/etc/apt/sources.list.d/ubuntu.sources').unlink(missing_ok=True)
    Path('/etc/apt/sources.list.d/mobile-build.sources').write_text(
        f'Types: deb deb-src\nURIs: {mirror}\n'
        f'Suites: {lock["suite"]} {lock["suite"]}-updates {lock["suite"]}-security\n'
        'Components: main universe restricted multiverse\n'
        'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n')
    run('apt-get', '-o', 'APT::Update::Error-Mode=any', 'update')
    run('apt-get', 'install', '-y', '--no-install-recommends', 'build-essential',
        'devscripts', 'equivs', 'git', 'ca-certificates', 'meson', 'ninja-build', 'dpkg-dev', 'pkgconf')
    sources = prepare(lock, work)
    for component in lock['components']:
        name = component['name']
        source = sources[name]
        packaging = work / (name + '-ubuntu')
        packaging.mkdir()
        # Exact source version, authenticated through Ubuntu's signed Sources index.
        run('apt-get', 'source', '--download-only', f'{name}={component["ubuntu_source_version"]}', cwd=packaging)
        dsc, = packaging.glob('*.dsc')
        run('dpkg-source', '--no-check', '--skip-patches', '-x', str(dsc), str(packaging / 'source'))
        # --no-check suppresses the uploader GPG-key check only: apt already
        # authenticated each source archive with the signed archive index.
        shutil.copytree(packaging / 'source/debian', source / 'debian')
        # Ubuntu's downstream patches target stock GNOME. Apply the reviewed
        # mobile tree as-is, while retaining Ubuntu's package split/dependencies.
        shutil.rmtree(source / 'debian/patches', ignore_errors=True)
        # Local compatibility fixes are versioned with the locked mobile stack.
        for patch in sorted((REPO / 'image/gnome-mobile/patches' / name).glob('*.patch')):
            run('patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch), cwd=source)
        if name == 'mutter':
            mobile_mutter_symbols(source)
        if name == 'gnome-shell':
            mobile_shell_dependencies(source)
        run('dch', '--newversion', lock['debian_version'], '--distribution', lock['suite'],
            '--force-distribution', 'Build the pinned GNOME Mobile source stack.', cwd=source,
            env={**os.environ, 'DEBFULLNAME': 'Galaxy S9+ Linux maintainers',
                 'DEBEMAIL': 'maintainers@example.invalid'})
        # Fail on packaging file drift or dependency failures. New mobile ABI
        # symbols are allowed; removed symbols still fail at check level 1.
        run('mk-build-deps', '--install', '--remove', '--tool',
            'apt-get -y --no-install-recommends -o Debug::pkgProblemResolver=yes',
            'debian/control', cwd=source)
        # Disable Meson's implicit network fetches. Every needed subproject is
        # pinned above; an omitted dependency must fail visibly.
        rules = source / 'debian/rules'
        text = rules.read_text()
        anchor = 'dh_auto_configure --'
        if anchor not in text:
            raise ValueError(f'{name}: packaging configure rule changed')
        text = text.replace(anchor, anchor + ' --wrap-mode=nodownload')
        text = text.replace('export DPKG_GENSYMBOLS_CHECK_LEVEL = 4',
                            'export DPKG_GENSYMBOLS_CHECK_LEVEL = 1')
        # Keep building the packaged test binaries, but do not run display/TTY
        # integration tests in the container. Debian's Mutter override does
        # not itself honor nocheck and otherwise ignores failed tests.
        if name == 'mutter':
            old = ('override_dh_auto_test-arch:\n\tdebian/tests/ensure-x11-dir\n'
                   '\t-$(TEST_COMMAND)\n\t-$(TEST_COMMAND_FLAKY) --logbase flaky-tests\n')
            if old not in text:
                raise ValueError('Mutter test override changed; review it')
            text = text.replace(old, 'override_dh_auto_test-arch:\n')
        rules.write_text(text)
        # Corresponding source, including packaging and vendored subprojects.
        run('tar', '-C', str(work), '-cJf', str(out / f'{name}-{lock["version"]}-source.tar.xz'), name)
        run('dpkg-buildpackage', '-b', '-uc', '-us', cwd=source)
        debs = sorted(work.glob('*.deb'))
        if not debs:
            raise ValueError(f'{name}: no binary packages built')
        run('apt-get', 'install', '-y', '--no-install-recommends', *map(str, debs))
        for file in work.iterdir():
            if file.suffix in ('.deb', '.ddeb', '.buildinfo', '.changes'):
                shutil.move(str(file), out / file.name)
    run('pkg-config', '--exact-version=' + lock['version'], 'libmutter-51')
    version = subprocess.check_output(['gnome-shell', '--version'], text=True)
    if lock['version'] not in version:
        raise ValueError('Built shell does not report the locked mobile version')
    shutil.copyfile(lockpath, out / 'sources.json')
    (out / 'build-packages.txt').write_bytes(subprocess.check_output(['dpkg-query', '-W']))
    checksums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                        for p in sorted(out.iterdir()) if p.is_file())
    (out / 'SHA256SUMS').write_text(checksums)


if __name__ == '__main__':
    main()
