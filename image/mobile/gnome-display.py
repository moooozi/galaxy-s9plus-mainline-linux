#!/usr/bin/python3
"""Initialize the phone panel to FHD+ at 250% once per GNOME user."""
from pathlib import Path
import time
import dbus

marker = Path.home() / '.config/s9plus-gnome-display-initialized'
if marker.exists():
    raise SystemExit(0)
for attempt in range(30):
    try:
        display = dbus.Interface(dbus.SessionBus().get_object(
            'org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig'),
            'org.gnome.Mutter.DisplayConfig')
        serial, monitors, logical, properties = display.GetCurrentState()
        # Do not overwrite a user's external-monitor layout.
        if len(monitors) != 1 or monitors[0][0][0] != 'DSI-1':
            raise SystemExit('Skipping initial scale: not a single DSI-1 panel')
        mode = next((mode for mode in monitors[0][1]
                     if int(mode[1]) == 1080 and int(mode[2]) == 2220), None)
        if mode is None or 2.5 not in mode[5]:
            raise SystemExit('DSI-1 does not advertise FHD+ at 250%')
        if (not mode[6].get('is-current') or len(logical) != 1
                or float(logical[0][2]) != 2.5):
            display.ApplyMonitorsConfig(serial, dbus.UInt32(2),
                dbus.Array([(dbus.Int32(0), dbus.Int32(0), dbus.Double(2.5),
                             dbus.UInt32(0), dbus.Boolean(True),
                             dbus.Array([('DSI-1', mode[0], dbus.Dictionary({}, signature='sv'))],
                                        signature='(ssa{sv})'))], signature='(iiduba(ssa{sv}))'),
                dbus.Dictionary({}, signature='sv'))
        marker.parent.mkdir(exist_ok=True)
        marker.touch()
        break
    except dbus.DBusException:
        time.sleep(2)
else:
    raise SystemExit('Could not initialize GNOME FHD+ display')
