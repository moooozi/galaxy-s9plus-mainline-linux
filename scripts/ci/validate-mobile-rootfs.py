#!/usr/bin/env python3
"""Validate a finished mobile rootfs before emitting its disk image."""
import json
from pathlib import Path
import subprocess
import sys


def validate(root, variant, manifest_path):
    root = Path(root)
    manifest = json.loads(Path(manifest_path).read_text())
    def command(*args):
        return subprocess.check_output(['chroot', str(root), *args], text=True).strip()
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require('VERSION_ID="26.10"' in (root / 'etc/os-release').read_text(), 'Wrong Ubuntu release')
    require(not command('dpkg', '--audit'), 'Package audit failed')
    require((root / 'lib').readlink() == Path('usr/lib'), 'Broken merged-/usr')
    require((root / 'lib/ld-linux-aarch64.so.1').exists(), 'Missing ELF loader')
    require(not list((root / 'etc/ssh').glob('ssh_host_*')), 'Pre-generated SSH host keys')
    require(not (root / 'usr/bin/qemu-aarch64-static').exists(), 'QEMU left in image')
    require('PAN_MAX_AFBC_PACKING_RATIO=0' in (root / 'etc/environment').read_text(), 'Missing GPU workaround')
    require('LIBGL_ALWAYS_SOFTWARE=1' not in (root / 'etc/environment').read_text(), 'Software rendering forced')
    require(command('passwd', '-S', 'root').split()[1] == 'L', 'Root account not locked')
    for module in ('fuse', 'snd-zrn-abox', 'hci_uart', 'zrn-bt'):
        vermagic = command('modinfo', '-k', manifest['release'], '-F', 'vermagic', module)
        require(vermagic.startswith(manifest['release'] + ' '), f'Wrong {module} kernel release')
    for service in ('NetworkManager', 'first-boot-ssh-keys', 'grow-rootfs', 'usb-gadget',
                    's9p-touch-power', 's9p-stability', 's9p-wifi-guard', 's9plus-audio', 's9plus-bluetooth'):
        require(command('systemctl', 'is-enabled', service + '.service') == 'enabled', f'{service} is disabled')
    for target in ('sleep', 'suspend', 'hibernate', 'hybrid-sleep', 'suspend-then-hibernate'):
        require((root / f'etc/systemd/system/{target}.target').readlink() == Path('/dev/null'), f'{target} unmasked')
    if variant == 'kde':
        for executable in ('plasma-open-settings', 'startplasmamobile', 'kscreen-doctor'):
            require((root / 'usr/bin' / executable).is_file(), f'Missing {executable}')
        require(not (root / 'usr/bin/gnome-shell').exists(), 'GNOME Shell leaked into KDE image')
        require(not (root / 'usr/share/wayland-sessions/gnome.desktop').exists(), 'GNOME session leaked into KDE image')
        require(command('systemctl', 'is-enabled', 'sddm.service') == 'enabled', 'SDDM disabled')
        require('Session=plasma-mobile.desktop' in (root / 'etc/sddm.conf.d/10-mobile.conf').read_text(), 'Wrong KDE autologin session')
        for setting, module in [('nightcolor', 'kcm_nightlight'), ('keyboardtoggle', 'kcm_virtualkeyboard')]:
            qml = root / f'usr/share/plasma/quicksettings/org.kde.plasma.quicksetting.{setting}/contents/ui/main.qml'
            require('plasma-open-settings ' + module in qml.read_text(), f'Broken {setting} quick setting')
    elif variant == 'gnome':
        lock = json.loads((Path(__file__).resolve().parents[2] / 'image/gnome-mobile/sources.json').read_text())
        require(lock['version'] in command('gnome-shell', '--version'), 'Stock GNOME Shell installed')
        # --version never loads Shell's JavaScript. These mobile-only imports
        # otherwise abort Shell or leave quick settings broken on first boot.
        command('gjs', '-c',
                "for (const [name, version] of Object.entries({GnomeAutoar: '0.1', "
                "ModemManager: '1.0', Atspi: '2.0', NM: '1.0', NMA4: '1.0'})) { "
                "imports.gi.versions[name] = version; void imports.gi[name]; }")
        for package in ('at-spi2-core', 'libpam-gnome-keyring', 'evolution-data-server'):
            require(command('dpkg-query', '-W', '-f', '${db:Status-Status}', package) ==
                    'installed', f'Missing GNOME integration: {package}')
        require(not (root / 'usr/bin/startplasmamobile').exists(), 'Plasma leaked into GNOME image')
        require('FallbackSession=gnome' in (root / 'etc/gdm3/custom.conf').read_text(), 'Wrong GDM fallback')
        wakeup = root / 'etc/systemd/user/org.gnome.Shell@.service.d/20-s9plus-touch-wakeup.conf'
        require('MUTTER_TOUCHSCREEN_WAKEUP=double-tap' in wakeup.read_text(),
                'Touchscreen wake is not enabled for the phone session')
        require((root / 'usr/share/wayland-sessions/gnome.desktop').is_file(), 'Missing GNOME session')
        schema = root / 'usr/share/glib-2.0/schemas/org.gnome.shell.gschema.xml'
        require('app-picker-layout-mobile' in schema.read_text(), 'Mobile Shell schema absent')
        require('toggle-blank' in command('gsettings', 'range', 'org.gnome.settings-daemon.plugins.power', 'power-button-action'), 'Mobile power-button behavior absent')
        require(command('systemctl', 'is-enabled', 'gdm.service') == 'enabled', 'GDM disabled')
    else:
        raise ValueError('Unknown image variant')
    print(f'{variant} mobile rootfs checks passed; hardware behavior still needs a phone test')


if __name__ == '__main__':
    validate(*sys.argv[1:])
