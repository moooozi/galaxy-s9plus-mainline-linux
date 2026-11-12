#!/usr/bin/env python3
"""Summarize capture-idle.py endpoints; never equate charging current to load."""
import json
from pathlib import Path
import sys


def interrupts(text):
    result = {}
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 9 or not all(x.isdigit() for x in fields[1:9]):
            continue
        result[fields[0] + ' ' + ' '.join(fields[9:])] = sum(map(int, fields[1:9]))
    return result


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    a, b = data['before'], data['after']
    fa, fb = a['files'], b['files']
    if fa['/proc/sys/kernel/random/boot_id'] != fb['/proc/sys/kernel/random/boot_id']:
        raise SystemExit('Reject capture across different boots')
    elapsed = b['monotonic'] - a['monotonic']
    print(data['note'])
    print(f'Interval: {elapsed:.3f}s; display: {a["display_power_save"]} -> {b["display_power_save"]}')
    if a['display_power_save'] != '(<3>,)' or b['display_power_save'] != '(<3>,)':
        print('REJECT as screen-off baseline: display was not off at both endpoints.')
    else:
        print('Screen off at both endpoints; inspect journal for intermediate wakes.')
    charger = '/sys/class/power_supply/max77705-charger/uevent'
    if charger in fa and charger in fb:
        for label, files in (('before', fa), ('after', fb)):
            values = dict(line.split('=', 1) for line in files[charger].splitlines() if '=' in line)
            print(f'Charger online {label}: {values.get("POWER_SUPPLY_ONLINE", "unknown")}')
    for cpu in (2, 3):
        prefix = f'/sys/devices/system/cpu/cpu{cpu}/cpuidle/state1/'
        residency = (int(fb[prefix+'time']) - int(fa[prefix+'time'])) / 1e6
        entries = int(fb[prefix+'usage']) - int(fa[prefix+'usage'])
        print(f'CPU{cpu}: C2 {residency/elapsed:.2%}; {entries} entries ({entries/elapsed:.1f}/s)')
    ia, ib = (interrupts(f['/proc/interrupts']) for f in (fa, fb))
    print('Largest interrupt deltas (includes IPIs):')
    for key in sorted(ia.keys() & ib.keys(), key=lambda k: ib[k]-ia[k], reverse=True)[:12]:
        delta = ib[key] - ia[key]
        print(f'  {delta/elapsed:9.2f}/s {delta:9d} {key}')
    sa, sb = (f['/proc/stat'].splitlines()[0].split()[1:] for f in (fa, fb))
    ticks = [int(y)-int(x) for x, y in zip(sa, sb)]
    print(f'Aggregate CPU busy (excluding iowait): {1-(ticks[3]+ticks[4])/sum(ticks[:8]):.2%}')
    for name in ('g0_irqs', 'mct_late_events'):
        key = '/sys/module/s9plus_cpuidle/parameters/' + name
        print(f'{name} delta: {int(fb[key])-int(fa[key])}')
    print('Endpoint battery data only; charging current is not device consumption.')


if __name__ == '__main__':
    main()
