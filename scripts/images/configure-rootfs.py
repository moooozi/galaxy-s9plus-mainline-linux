#!/usr/bin/env python3
"""Apply distribution-independent phone setup to an assembled rootfs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]


def install_file(root, source, target=None, mode=None):
    target = root / (target or str(source.relative_to(REPO / 'device/base')))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode if mode is not None else
                 (0o600 if target.suffix == ".nmconnection" else source.stat().st_mode & 0o777))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('variant', choices=('debian-embedding','postmarketos-plasma','postmarketos-phosh'))
    args = parser.parse_args()
    root = args.root.resolve()
    desktop = args.variant != 'debian-embedding'
    overlay = REPO / 'image/debian/rootfs'
    for source in overlay.rglob('*'):
        if source.is_file():
            install_file(root, source, str(source.relative_to(overlay)))
    base = REPO / 'device/base'
    for relative in ('usr/local/sbin/usb-gadget', 'etc/default/usb-gadget',
                     'etc/systemd/system/usb-gadget.service',
                     'etc/NetworkManager/conf.d/10-usb-gadget.conf',
                     'etc/NetworkManager/conf.d/usb0-managed.conf',
                     'etc/udev/rules.d/70-s9plus.rules'):
        install_file(root, base / relative)
    # Only firmware already redistributable in the existing port is copied.
    for source in (base / 'lib/firmware/brcm').iterdir():
        if source.is_file():
            install_file(root, source, 'usr/lib/firmware/brcm/' + source.name, 0o644)
    if desktop:
        for directory in ('usr/share/s9plus-charging',):
            shutil.copytree(base / directory, root / directory, dirs_exist_ok=True)
        for relative in ('usr/lib/systemd/system-generators/s9plus-charging-generator',
                         'usr/local/sbin/s9plus-offline-charging',
                         'etc/systemd/system/s9plus-offline-charging.service',
                         'etc/systemd/system/s9plus-offline-charging.target'):
            install_file(root, base / relative)
    # This image boots directly from the kernel's embedded initramfs into
    # USERDATA; no separate distro boot partition or generated boot.img.
    (root / 'etc/fstab').write_text('/dev/disk/by-partlabel/USERDATA / ext4 defaults,noatime 0 1\n')
    (root / 'etc/hostname').write_text('s9plus\n')
    (root / 'etc/hosts').write_text('127.0.0.1 localhost\n127.0.1.1 s9plus\n::1 localhost ip6-localhost\n')
    (root / 'etc/machine-info').write_text('CHASSIS=' + ('handset' if desktop else 'embedded') + '\n')
    cfg = root / 'etc/s9plus'
    cfg.mkdir(parents=True, exist_ok=True)
    if desktop:
        (cfg / 'first-boot.json').write_text(json.dumps({'user':'user','fallback_password':'147147','force_password_change':False})+'\n')
        (cfg / 'first-boot.json').chmod(0o600)
    # Sensor wakelock shim and deeper CPU/system sleep remain unvalidated.
    for target in ('sleep','suspend','hibernate','hybrid-sleep','suspend-then-hibernate'):
        path = root / f'etc/systemd/system/{target}.target'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        path.symlink_to('/dev/null')
    # Use the existing CPU guard, with no automatic wider idle enablement.
    services = ['NetworkManager.service', 'usb-gadget.service', 's9plus-first-boot.service',
                's9plus-cpuidle.service', 's9plus-battery-settings.service', 'avahi-daemon.service']
    ssh_service = 'ssh.service' if not desktop else 'sshd.service'
    if desktop:
        drop = root / 'etc/systemd/system/sshd.service.d'
        drop.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'etc/systemd/system/ssh.service.d/10-first-boot.conf',drop / '10-first-boot.conf')
        services += ['s9plus-audio.service','s9plus-bluetooth.service','s9plus-sensors.service']
        bt = root / 'etc/systemd/system/s9plus-bluetooth.service.d'
        bt.mkdir(parents=True, exist_ok=True)
        (bt / '10-own-address.conf').write_text('[Unit]\nConditionPathExists=/var/lib/s9plus-bluetooth/bt_addr\n')
        if args.variant == 'postmarketos-plasma':
            services += ['sddm.service']
        else:
            services += ['greetd.service']
    if desktop:
        display = 'sddm' if args.variant == 'postmarketos-plasma' else 'greetd'
        drop = root / f'etc/systemd/system/{display}.service.d'
        drop.mkdir(parents=True, exist_ok=True)
        (drop / '10-first-boot.conf').write_text('[Unit]\nRequires=s9plus-first-boot.service\nAfter=s9plus-first-boot.service\n')
    subprocess.run(['chroot', str(root), 'systemctl', 'set-default', 'graphical.target' if desktop else 'multi-user.target'], check=True)
    services += [ssh_service]
    subprocess.run(['chroot', str(root), 'systemctl', 'enable', *services], check=True)
    subprocess.run(['chroot', str(root), 'systemctl', 'enable', 'serial-getty@ttyGS0.service'], check=True)
    # The initramfs uses /sbin/init on both distributions.
    if not (root / 'sbin/init').exists():
        init = root / 'sbin/init'
        if not init.is_symlink():
            init.symlink_to('/usr/lib/systemd/systemd')
    for path in (root / 'etc/ssh').glob('ssh_host_*'):
        path.unlink()
    (root / 'etc/machine-id').write_text('')
    (root / 'var/lib/dbus/machine-id').unlink(missing_ok=True)
    profile = root / 'usr/share/s9plus-image'
    profile.mkdir(parents=True, exist_ok=True)
    (profile / 'profile.json').write_text(json.dumps({'variant':args.variant,'kernel_repository':'moooozi/galaxy-s9plus-kernel'},indent=2)+'\n')


if __name__ == '__main__':
    main()
