# Galaxy S9+ CPU idle integration

The current driver lives in `src/cpuidle/` and is built into the kernel with
`CONFIG_S9PLUS_CPUIDLE=y`. It calls the architecture suspend/resume interfaces
directly; the build no longer packages the experimental private-symbol module.
`driver/` preserves the historical module for provenance/rollback research only.
C2 starts disabled (`CPUIDLE_FLAG_OFF`). The rootfs helper checks the durable
failure marker and driver identity, schedules independent confirmation, then
enables CPUs2/3 through the standard cpuidle `disable` attributes. It never
reads kallsyms or passes function addresses into a module. A failed startup
leaves the marker and rolls back partial enablement.

The built-in MCT clockevent is registered with C2 still disabled. Initial
comparator state is cleared before installing its IRQ, the IRQ stays on CPU0,
and comparator write/deadline failures propagate rather than reporting a
usable wake event. Full-kernel compilation and source checks passed; the
November12 hardware trial is tracked in the installation status.

## Earlier module validation


Installed and enabled on the SM-G965F's exact `7.3.1-s9plus` kernel. Both cores
passed 100 pinned 10 ms timer wakeups (about 1.025 seconds per core), short
load/idle transitions, independent two-minute confirmation and normal reboot.
C2 usage/residency and MCT G0 IRQs advance; no late events were observed.
GNOME and Wi-Fi SSH stayed healthy. Temperature/battery savings and system
suspend have not been established.

The driver offers WFI and context-losing C2 on **A55 CPUs 2 and 3 only**.
CPU0 remains available to run the hardware broadcast timer. Wider masks are
rejected. A read-only diagnostic confirmed collisions in the original suspend
hash; `patch-suspend-hash.py` corrects the star2lte save/resume affinity mapping.
Kernel #6 booted with this correction and passed fresh pinned timer/load tests,
sensor/desktop recovery and the independent two-minute C2 confirmation. The
correction alone does not establish safe idle on additional cores; separate
tests are required before expansion.

The difference from the failed PSCI DT experiments is the flexible-PMU
CPU_INFORM/wake-line sequence and explicit `cpu_resume` entry address. MCT G0
continues ticking when a powered-down core's architectural timer stops, and
sends the broadcast wake interrupt through CPU0. See [SOURCE.md](SOURCE.md).

Build the current driver with the kernel through `scripts/build/apply_drivers.sh`.
The separate sensor-module helper no longer compiles CPU idle. The guarded
CPU-idle service remains the userspace enablement policy. The DT idle states, CPU/GPU voltage stability defaults,
masked sleep targets and charger boot remain unchanged.

## First phone test

After installing the built-in kernel, matching helper and unit, with the phone in reach,
a charger connected, working USB SSH and the existing watchdog/recovery intact:

```sh
sudo systemctl daemon-reload
sudo systemctl start s9plus-cpuidle.service
grep -H . /sys/devices/system/cpu/cpu{2,3}/cpuidle/state1/{name,usage,time}
cat /sys/module/s9plus_cpuidle/parameters/{g0_irqs,mct_late_events}
sudo journalctl -k --no-pager
```

Test SSH responsiveness and per-core timed waits/load followed by idle; both
C2 usage counters and MCT G0 IRQs must advance. The helper schedules an
independent confirmation after 120 seconds, then requires fresh counter
progress before removing `/var/lib/s9plus-cpuidle/loading`. A failed boot/load
leaves this marker and blocks future attempts. Do not clear it automatically.
An idle counter alone does not prove the actual PMU powered the core down;
inspect PMU state/residency as part of hardware validation.

For rollback, disable the service and reboot. The clockevent is built in and cannot be unloaded. `/etc/s9plus-cpuidle.disable` prevents service
startup. Enable persistent startup only after the live trial and a reboot pass.
Full system suspend, cluster powerdown and CPU hotplug remain disabled.

## Idle measurements

`capture-idle.py OUTPUT --note DESCRIPTION` records two read-only snapshots
120 seconds apart after a 15-second settling period, without interval polling.
Run detached from SSH as root; record cable, network and screen conditions in
the note and avoid interacting with the device. It reads CPU residency, IRQs,
battery/thermal endpoints, display state and runtime PM without changing policy.
`summarize-idle.py OUTPUT` reports deltas. Inspect the raw conditions: endpoint
agreement alone cannot prove that the screen stayed off throughout the interval.
Battery current while charging is not whole-device consumption.

The first two captures on November 4 were interrupted by screen wake and are
not valid screen-off baselines. They measured about 996 audio DSP IRQ/s even
with both playback streams closed, and about 98–99% C2 residency on CPUs2/3.
The audio source and its 1ms mailbox polling thread warrant investigation;
no audio power change or battery-saving claim follows from those observations.
