# Known issues

Honest list. Everything here has been reproduced on the device.

## CPU idle: A55 CPUs 2 and 3 work; wider idle remains unsupported

A port of ztOS's flexible-PMU C2 sequence and MCT hardware broadcast timer is
now built into the kernel from `src/cpuidle/`;
[`experiments/cpuidle`](../experiments/cpuidle/README.md) documents the bring-up.
It is installed and enabled on this S9+ for `7.3.1-s9plus`, accepting only
A55 CPUs 2 and 3. Both cores passed 100 pinned 10 ms timer wakeups, load/idle
transitions, independent two-minute confirmation and a normal reboot. C2
counters and MCT G0 IRQs advance; late-event count stayed zero. GNOME and Wi-Fi
SSH remained active. The November12 built-in kernel#8 also passed the pinned waits and independent
confirmation with zero MCT write failures/late events. C2 starts disabled; the
persistent userspace guard enables only the validated cores through cpuidle
sysfs. No kallsyms or private function-address module parameters are required.
No whole-device power saving is claimed. No deeper DT
states, cluster powerdown, hotplug, system suspend or voltage reductions are
enabled. Other cores retain WFI. Future images enable the conservative service.

The following failures describe the earlier DT-based attempts and remain
relevant constraints, rather than proof the built-in driver succeeds or fails.

Deep CPU idle remains a major power-management gap. Only CPUs2/3 have the
validated C2 state; other cores use `WFI`. The contribution of each powered block to idle temperature has not been
isolated with a whole-device power measurement.

Kernel #6 corrects confirmed star2lte A55 suspend-context hash aliases. Raw
MT-style A55 identities are normalized to firmware/DT affinity before hashing
on both save and resume. The patched assembly gives all eight cores distinct
context slots; live tests retain the validated CPUs2/3 mask. This removes one
known blocker, without establishing broader core/cluster or SoC idle. Activity
captures also found about996audio DSP interrupts/s with closed playback streams;
both captures were interrupted by screen wake, so neither establishes screen-off
power consumption. On November12 the new audio handler recognized these as
firmware fault reports, performed a bounded DSP restart, and the audio IRQ count
stayed unchanged during a120sdiagnostic interval. The underlying firmware fault
is unresolved; this observation is not a whole-device power measurement.

Four attempts, all reproduced:

| attempt | result |
|---|---|
| both clusters powerdown (`arm,psci-suspend-param = <0x10000>`) | boot hangs |
| little cluster only, big cluster with no idle state | boots, but `CPUidle PSCI: Failed to create psci-cpuidle device` -- `psci_cpuidle_probe()` walks every present CPU and aborts entirely when one has no DT idle state |
| big cluster given a retention state (`param = <0x0>`) so the probe has something for every CPU | boot hangs |
| CPU idle floor in cpufreq (hold an idle cluster at its lowest step) | booted on #150, #155 and #157; sampler pinned to A55 CPU0 on #155 and later |

The root causes of the suspend failures are unresolved. M3 hotplug previously
failed at assembly stage 7, but context-losing PSCI `CPU_SUSPEND` resumes through
`cpu_resume`; hotplug `CPU_OFF`/`CPU_ON` uses secondary entry. These are separate
paths and the hotplug failure does not prove the cause of the suspend failure.
Initial SMP bring-up works with the six vendor M3 PMU defaults and `maxcpus=8`.

Any further idle experiment needs separate resume instrumentation and DVFS/
cluster coordination. Do not enable the failed DT states at boot.

The device tree ships **without** deeper idle states. CPU idle frequency
flooring and GPU per-step voltage are both **off** (since 2026-09-23):

    s9p_cpufreq.idle_floor=1    hold an idle cluster at its lowest step
    s9p_g3d.step_volt=1         lower BUCK6 on the lower GPU clock steps

With both on, kernel #163 froze roughly once a day on an idle desktop:
seven hard hangs in a week, the journal simply stops, and three of them
never came back without a manual reset. Both switches lower voltages only
while idle (M3 at 400 MHz / 700 mV, a step no load test covered); their
validation ran 30-120 s. Kernels built before this change default to on,
so `s9p-stability.service` writes `N` to both at every boot.

The optional flight recorder ([`extras/flight-recorder`](../extras/flight-recorder/))
writes every kernel message and a state line per minute (clocks, rail,
temperatures, Wi-Fi) to `/var/log/s9p-blackbox.log`, fsync'ed. The journal
does not keep kernel messages of a boot that hung, so after a freeze that
file is where the last minute is.

## Sensors: revised reset passes two warm reboots; calibration pending

[`experiments/sensors`](../experiments/sensors/README.md) ports the BCM4773
transport and firmware service from ztOS. Light, accelerometer and gyro samples
are published through real IIO devices for the standard `iio-sensor-proxy`.
The transport and IIO modules load on the phone. Its owner-provided Android
runtime mounts read-only; vendor `lhd` runs with vendor libraries and a private
legacy-wakelock shim (system suspend must stay masked). Firmware downloading
works after a passage through TWRP. Corrected SSP write accounting and firmware
gyro-frame sizes allow continuous real IIO samples. SensorProxy detects light
and acceleration, and GNOME rotation is user-observed; the mount matrix is
being calibrated with physical feedback. A normal warm reboot initially
reproduced `ROM SYNC failure`; parking the hub pins and removing its dedicated
supply at shutdown passed the subsequent normal-reboot test. A later November4
boot failed ROM synchronization again, and a bounded supply-cut trial on
November12 also failed. The shutdown fix does not establish reliable startup.
The durable failed-initialization marker intentionally blocks automatic retries.
Recovery pinctrl then exposed missing SCK/MOSI pull-downs: the revised transport
explicitly drives those AP outputs low while retaining MISO as an input. It
passed two consecutive normal reboots after TWRP recovery on November 12, with
live light/motion samples and automatic firmware loading. These observed tests
do not establish every future startup condition. Device
dependencies prevent mounting before SYSTEM/VENDOR links appear. The reader
is enabled with a failed-initialization guard. Auto-brightness, camera and GNSS
are not claimed to work.

## Wi-Fi drops and never comes back

A failed group rekey (`EAPOL-Key Replay Counter did not increase`) makes
NetworkManager ask for a new password; with no secret agent it ends in
`no-secrets` and never retries. `s9p-wifi-guard.service` (part of the image)
reconnects after a minute. Wi-Fi power save is off in NetworkManager. Where
the 5 GHz signal is weak, pinning the connection to 2.4 GHz (`nmcli connection
modify <name> 802-11-wireless.band bg`) made the reference phone's link far
more stable.

## No suspend

Suspend cannot resume (the M3 cores do not come back), so every sleep
target is masked and `AllowSuspend=no`.

See [07-validation.md](07-validation.md) for the CPU/GPU measurements and
the parameter state they were taken with.

## GPU power-off recovery history

On #155, setting `s9p_g3d_pd.always_on=N` resulted in a partial power-down
(`STATUS=002f000e`) and an SError on the next Panfrost reset. Pstore was recovered
from TWRP. The missing vendor secure-save step and five G3D PMU low-power
initialization settings were added. #160 completed repeated full off/on and
render cycles; #162 boots with this enabled by default. `always_on=Y` remains
the recovery override. See [07-validation.md](07-validation.md) for job faults
that remain separate from the repaired power-domain timeout.

## Screen transfer

The 9 FPS bottleneck of a 1080p GNOME screen-cast (see
[05-performance.md](05-performance.md)) was later worked around with a
capture path that reached about 51 FPS in an animated 1080p test.

## gnome-shell restarts in the first minute

A `SIGSEGV` inside Mesa/EGL (stack in `libgallium` / `libEGL_mesa`), not a
kernel-reported fault. It settles after a few restarts and then runs.

## Warm reboots hang early

Roughly every second warm restart stops early in boot. The watchdog is the
mitigation, not the fix: WDT1 is armed from the first boot instruction
(`s3c2410_wdt.tmr_atboot=1 tmr_margin=60`) and systemd takes over with
`RuntimeWatchdogSec=30s` once userspace is up, so a hang turns into a reboot
instead of a dead phone.

For this to work at all the PMU's `MASK_WDT_RESET_REQUEST` has to be cleared
-- see [04-drivers.md](04-drivers.md).

## Reading the sboot framebuffer resets the SoC

Mapping `0xcc000000` through `/dev/mem` resets the phone (`RST_STAT
0x10000`). Read the **live** scanout address out of DECON's IDMA register
instead.

## s9p-acpm info crashes

One channel entry lies in a faulting SRAM page. `read`, `write`, `update` and
`tsp` work.

## No snap

`CONFIG_SQUASHFS` does not build in this tree, so snaps cannot mount. Install
`gnome-shell` + `ubuntu-session` + Yaru + `gnome-shell-extension-ubuntu-dock`
rather than `ubuntu-desktop`, or GNOME looks like bare Debian.

Practical consequence: Thunderbird has no arm64 package outside snap. Evolution
is the substitute that works.

## Things that look like bugs and are not

* **glmark2 is clean while the desktop shows artefacts.** That is the texture
  path, not a contradiction. See [05-performance.md](05-performance.md).
* **`KNOX_NCM` cannot be turned off** in the old 4.9 tree -- the network core
  calls `check_ncm_flag()` and `knox_collect_conntrack_data()`
  unconditionally, so `vmlinux` does not link without it. Only relevant if you
  go back to the downstream kernel.
* **A mainline kernel that does nothing at all** is the `text_offset` trap.
  See [02-building.md](02-building.md).
