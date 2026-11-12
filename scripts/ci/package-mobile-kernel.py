#!/usr/bin/env python3
"""Package a uniLoader BOOT image and its matching, verified module set."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request

REPO = Path(__file__).resolve().parents[2]
MODULE_PATHS = [
    'fs/fuse/fuse.ko', 'sound/soundcore.ko', 'sound/core/snd.ko',
    'sound/core/snd-timer.ko', 'sound/core/snd-pcm.ko',
    'drivers/i2c/algos/i2c-algo-bit.ko', 'drivers/i2c/busses/i2c-gpio.ko',
    'net/bluetooth/bluetooth.ko', 'net/bluetooth/rfcomm/rfcomm.ko',
    'net/bluetooth/bnep/bnep.ko', 'net/bluetooth/hidp/hidp.ko',
    'drivers/bluetooth/btbcm.ko', 'drivers/bluetooth/hci_uart.ko',
    'crypto/kpp.ko', 'crypto/ecc.ko', 'crypto/ecdh_generic.ko', 'crypto/cmac.ko',
    'crypto/aes.ko', 'drivers/hid/hid.ko', 'drivers/hid/hid-generic.ko', 'drivers/hid/uhid.ko',
    'drivers/iio/industrialio.ko',
]


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    work, destination, selection = map(lambda path: Path(path).resolve(), sys.argv[1:])
    src = work / 'src/mainline'
    out = src / 'out'
    manifest = json.loads(selection.read_text())
    compat = destination / 'libwakelock-no-suspend.so'
    shutil.copyfile(work / 'sensors-compat/libwakelock-no-suspend.so', compat)
    manifest['sensor_compat_sha256'] = sha256(compat)
    release = (out / 'include/config/kernel.release').read_text().strip()
    if release != manifest['version'] + '-s9plus':
        raise ValueError(f'Kernel release mismatch: {release}')
    stage = work / 'module-stage'
    modules = stage / 'usr/lib/modules' / release
    modules.mkdir(parents=True)
    (stage / 'lib').symlink_to('usr/lib')  # Only for host depmod; never archived.
    for relative in MODULE_PATHS:
        target = modules / 'kernel' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / relative, target)
    for kind, name in [('audio', 'snd-zrn-abox.ko'), ('bluetooth', 'zrn-bt.ko'),
                       ('sensors', 'zrn-bbd.ko'), ('sensors', 's9plus-sensor-iio.ko')]:
        target = modules / f'extra/s9plus-{kind}' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / f'{kind}-driver' / name, target)
    module_manifest = []
    for path in sorted(modules.rglob('*.ko')):
        vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(path)], text=True).strip()
        if not vermagic.startswith(release + ' '):
            raise ValueError(f'{path}: wrong vermagic {vermagic}')
        module_manifest.append({'path': str(path.relative_to(stage)),
                                'sha256': sha256(path), 'vermagic': vermagic})
    for name in ('modules.builtin', 'modules.builtin.modinfo'):
        shutil.copyfile(out / name, modules / name)
    (modules / 'modules.order').write_text(''.join(
        str(path.relative_to(modules)) + '\n' for path in sorted(modules.rglob('*.ko'))))
    result = subprocess.run(['depmod', '-e', '-F', str(out / 'System.map'),
                             '-b', str(stage), release], text=True, capture_output=True, check=True)
    if 'unknown symbol' in result.stderr:
        raise ValueError(result.stderr)
    (destination / 'depmod.log').write_text(result.stdout + result.stderr)
    with tarfile.open(destination / 'modules.tar.gz', 'w:gz') as archive:
        for path in sorted(modules.rglob('*')):
            if path.is_file():
                info = archive.gettarinfo(str(path), str(path.relative_to(stage)))
                info.uid = info.gid = 0
                info.uname = info.gname = 'root'
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
    raw = work / 'boot-inputs'
    raw.mkdir()
    image = bytearray((out / 'arch/arm64/boot/Image').read_bytes())
    if image[56:60] != b'ARM\x64':
        raise ValueError('Not an ARM64 Image')
    struct.pack_into('<Q', image, 8, 0x80000)
    (raw / 'Image').write_bytes(image)
    shutil.copyfile(out / 'arch/arm64/boot/dts/exynos/exynos9810-star2lte.dtb',
                    raw / 'exynos9810-star2lte.dtb')
    # pack_uniloader consumes a complete archived raw BOOT image.
    subprocess.run(['python3', str(REPO / 'scripts/build/mkdtbh.py'), '-o', str(raw / 'dt.img'),
                    '-s', '2048', str(raw / 'exynos9810-star2lte.dtb')], check=True)
    import gzip
    (raw / 'ramdisk.gz').write_bytes(gzip.compress(b'', mtime=0))
    subprocess.run(['python3', str(REPO / 'scripts/build/mkboot.py'), '--kernel', str(raw / 'Image'),
                    '--dt', str(raw / 'dt.img'), '--ramdisk', str(raw / 'ramdisk.gz'),
                    '--cmdline', 'console=tty0', '-o', str(raw / 'boot.img')], check=True)
    template = work / 'twrp-template.img'
    request = urllib.request.Request(
        'https://dl.twrp.me/star2lte/twrp-3.3.1-0-star2lte.img',
        headers={'Referer': 'https://dl.twrp.me/star2lte/twrp-3.3.1-0-star2lte.img.html'})
    with urllib.request.urlopen(request, timeout=120) as response:
        template.write_bytes(response.read())
    if sha256(template) != '5b5d2290940203316024a94581107ffad17670bb2f596fd27ef483d3d2685994':
        raise ValueError('TWRP template checksum mismatch')
    import os
    subprocess.run(['bash', str(REPO / 'scripts/build/pack_uniloader.sh'),
                    str(raw), 'boot-s9plus-mobile.img'], check=True,
                   env={**os.environ, 'BUILD': str(work), 'TWRP_IMG': str(template)})
    boot = REPO / 'dist/uniloader/boot-s9plus-mobile.img'
    blob = boot.read_bytes()
    if len(blob) > 57671680 or not blob.endswith(b'SEANDROIDENFORCE'):
        raise ValueError('Invalid or oversized BOOT image')
    shutil.copyfile(boot, destination / 'boot-s9plus.img')
    shutil.copyfile(out / '.config', destination / 'kernel.config')
    manifest.update(release=release, modules=module_manifest, boot_sha256=sha256(boot),
                    port_commit=subprocess.check_output(['git', '-c', f'safe.directory={REPO}', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip())
    (destination / 'kernel-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    subprocess.run(['tar', '-C', str(src), '--exclude=./out', '-I', 'zstd -T0 -3',
                    '-cf', str(destination / 'kernel-source.tar.zst'), '.'], check=True)
    # Out-of-tree drivers and the loader/build scripts are also needed to
    # reconstruct BOOT and modules; preserve the actual checkout, including
    # local draft changes when validating before a commit.
    subprocess.run(['tar', '-C', str(REPO), '--exclude=__pycache__',
                    '-I', 'zstd -T0 -3', '-cf', str(destination / 'port-build-source.tar.zst'),
                    'scripts/build', 'scripts/ci', 'src',
                    'experiments/audio/driver', 'experiments/bluetooth/driver',
                    'experiments/sensors', 'experiments/cpuidle',
                    'experiments/bluetooth/patch-btbcm-s9plus.py',
                    'device/mainline-init-boot', 'device/mainline-extra-probe',
                    'bootloader/uniLoader', 'branding', 'firmware'], check=True)
    (destination / 'SHA256SUMS').write_text(''.join(
        f'{sha256(path)}  {path.name}\n' for path in sorted(destination.iterdir())
        if path.is_file() and path.name != 'SHA256SUMS'))


if __name__ == '__main__':
    main()
