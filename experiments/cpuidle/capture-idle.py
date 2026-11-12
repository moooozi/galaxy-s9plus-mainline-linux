#!/usr/bin/env python3
"""Read-only, endpoint-only idle capture. Run locally on the phone as root.

No policy changes. The caller must arrange/record screen and cable state.
Battery readings while charging are not whole-device consumption measurements.
"""
import argparse
import glob
import json
import os
from pathlib import Path
import subprocess
import time


def read(path):
    try:
        return Path(path).read_text()
    except OSError as exc:
        return {"error": str(exc)}


def snapshot():
    paths = ["/proc/stat", "/proc/interrupts", "/proc/net/dev",
             "/proc/sys/kernel/random/boot_id", "/sys/kernel/debug/wakeup_sources",
             "/sys/kernel/debug/clk/clk_summary", "/sys/kernel/debug/pm_genpd/pm_genpd_summary"]
    for pattern in ["/sys/devices/system/cpu/cpu*/cpuidle/state*/*",
                    "/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq",
                    "/sys/class/power_supply/*/uevent", "/sys/class/thermal/thermal_zone*/temp",
                    "/sys/module/s9plus_cpuidle/parameters/*",
                    "/sys/kernel/debug/dri/*/state", "/proc/asound/card*/pcm*/sub*/status"]:
        paths.extend(glob.glob(pattern))
    # sysfs contains parent/device/subsystem symlinks: never recurse through them.
    for directory, _, files in os.walk("/sys/devices/platform", followlinks=False):
        if directory.endswith("/power") and "runtime_status" in files:
            paths.append(directory + "/runtime_status")
    display = subprocess.run(
        ["runuser", "-u", "ubuntu", "--", "env",
         "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus", "gdbus", "call",
         "--session", "--dest", "org.gnome.Mutter.DisplayConfig", "--object-path",
         "/org/gnome/Mutter/DisplayConfig", "--method", "org.freedesktop.DBus.Properties.Get",
         "org.gnome.Mutter.DisplayConfig", "PowerSaveMode"],
        capture_output=True, text=True, timeout=10)
    return {"monotonic": time.monotonic(), "wall_time": time.time(),
            "display_power_save": display.stdout.strip(),
            "display_query_error": display.stderr.strip(),
            "files": {p: read(p) for p in sorted(set(paths)) if not Path(p).is_dir()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--settle", type=int, default=15)
    parser.add_argument("--note", required=True)
    args = parser.parse_args()
    if args.seconds < 1 or args.settle < 0:
        parser.error("seconds must be positive and settle nonnegative")
    time.sleep(args.settle)
    result = {"note": args.note, "method": "two snapshots, no interval polling",
              "before": snapshot()}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    time.sleep(args.seconds)
    result["after"] = snapshot()
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
