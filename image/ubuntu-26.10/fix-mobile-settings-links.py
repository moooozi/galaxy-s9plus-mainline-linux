#!/usr/bin/env python3
"""Fix two obsolete Plasma Mobile 6.7 quick-setting module names.

Run as root on the phone, or pass an offline rootfs directory as argv[1].
Original packaged files are kept next to each file for review/rollback.
"""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/')
base = root / 'usr/share/plasma/quicksettings'
for setting, old, new in [
    ('nightcolor', 'kcm_nightcolor', 'kcm_nightlight'),
    ('keyboardtoggle', 'kcm_mobile_onscreenkeyboard', 'kcm_virtualkeyboard'),
]:
    path = base / f'org.kde.plasma.quicksetting.{setting}/contents/ui/main.qml'
    source = path.read_text()
    old_command = f'plasma-open-settings {old}'
    new_command = f'plasma-open-settings {new}'
    if old_command not in source:
        if new_command not in source:
            raise SystemExit(f'Unexpected settings command in {path}')
        continue
    backup = path.with_name(path.name + '.before-settings-fix')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(source.replace(old_command, new_command))
    print(f'{setting}: {old} -> {new}')
