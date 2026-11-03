#!/usr/bin/python3
"""Set the single phone panel to scale 3 once per GNOME user."""
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
        mode = next(mode for mode in monitors[0][1] if mode[6].get('is-current'))
        # Mobile Mutter can already use scale 3 even when its advertised
        # fractional scale list omits it for the 2960-pixel panel height.
        if len(logical) != 1 or float(logical[0][2]) != 3.0:
            if 3.0 not in mode[5]:
                raise SystemExit('DSI-1 does not advertise scale 3')
            display.ApplyMonitorsConfig(serial, dbus.UInt32(2),
                dbus.Array([(dbus.Int32(0), dbus.Int32(0), dbus.Double(3.0),
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
    raise SystemExit('Could not initialize GNOME display scale')
