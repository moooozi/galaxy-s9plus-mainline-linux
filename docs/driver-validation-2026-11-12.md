# Galaxy S9+ driver validation — November 12, 2026

Physical device: SM-G965F/star2lte. The existing Ubuntu installation is the
hardware test system while the [Debian/postmarketOS plan](new-plan.md) is prepared.

## Tested artifacts

| Artifact | SHA256 |
| --- | --- |
| Kernel #8 BOOT, `7.3.1-s9plus`, built 20:56:11 UTC | `0d0001fbb0bd52b084415ea29077bf95fab17dd358e490efa2477797ffabaa9f` |
| Full pretrial BOOT partition backup | `409c224e09414e23b4a7b14275e9f2a358b258da57051fdff6a986ebb698e01b` |
| Audio fault-handling module | `1e43b6c24f50512252d060a926e24ad009648e0bd4f3dc671f5487aa8a160fc7` |
| Sensor transport with explicit output-low parking | `e8c7e02f270a8e43ffb06a38ff5b6398cd1a0fc668e8086aa3527c9235942014` |

The BOOT backup matched the live partition before installation. Candidate
readback matched its hash. The embedded DT/ramdisk, outer DT/ramdisk and tested
offline-charging loader configuration were preserved. RECOVERY and USERDATA
were not flashed. Original modules and CPU helper were backed up separately.

## CPU idle

The driver is built into the kernel and uses direct architecture suspend/resume
calls. C2 starts disabled; the persistent userspace guard enables only CPUs2/3.
First boot confirmed zero C2 entries before enablement. Each core then passed
100 pinned 10ms waits and a short load/idle transition. MCT IRQ affinity read
back as CPU0. The independent two-minute confirmation passed with fresh C2/G0
progress and no late deadlines or failed synchronized timer writes. Subsequent
boot confirmation also passed.

Host regressions execute the actual timer functions with failed MMIO handshakes,
expired deadlines and counter wrap. Guard tests cover stale boot markers,
partial enablement, scheduler failure and missing fresh G0 progress. The actual
patched AArch64 suspend-hash macros also pass under QEMU for all eight measured
MPIDRs and retain the unmodified path for other boards.

CPU1, M3 cores, CPU0 powerdown, cluster/SoC sleep, hotplug and system suspend are
not validated or enabled by this change. Wider CPU idle remains unfinished.

## Audio

The earlier near-1000/s IRQ activity included Samsung `ABOX_REPORT_FAULT`
messages, previously ignored. On kernel #8 the new handler caught an initial
firmware exception and the existing DSP restart path recovered once. The audio
IRQ count then remained at 67 across a 120.181 s capture with both playback streams
closed. Direct ALSA playback of a three-second, low-amplitude test tone completed;
the stream watchdog reported no recovery and there was no additional DSP restart.
This validates software playback completion, not a new audible confirmation.

The firmware exception's root cause remains unresolved. Recovery is bounded to
three attempts, captures raw diagnostics and quiesces further fault IRQs. It does
not enable audio-domain power cycling. Microphones and call audio remain outside
the supported playback configuration.

## Charging

The kernel boots with the existing charging settings. Live reads reported 500 mA
input limit, 450 mA charge current and 4.4 V configured float voltage. Inhibit/resume
sysfs writes succeeded; inhibit reported `Not charging`, and the original `auto`
policy was restored. Battery temperature was 32.2°C during the initial trial and
28.1°C after recovery.

Host C regressions cover current-field encoding boundaries, stuck/concurrently
modified AICL state and register-read failures. These checks do not validate
autonomous charge termination. The planned 65% embedding-kernel limit and fast
charging work are not implemented here.

## Sensors and desktop

The original shutdown fix was insufficient: a later November 4 boot and two
bounded November 12 trials failed firmware ROM synchronization. A TWRP passage
restored live light/motion publication. Recovery pinctrl confirmed no pulls on
SCK/MOSI; the new reset/shutdown path drives those host outputs low and keeps
MISO as an input. The revised module passed two consecutive normal reboots,
with automatic firmware loading and live light/motion samples. Their boot IDs
were `891fc328-3a50-42fe-bf44-35ba3b15cf6c` and
`a8b88588-8228-45f5-9dbf-4cb79f7556c5`. Physical orientation calibration remains
pending. Longer-term startup reliability is not established by two reboots.

The screen-off capture was rejected: the GNOME authentication/session worker
exited during the lock test and the greeter woke the display. The capture shows
roughly 95% C2 residency on CPUs2/3 and removal of the audio IRQ storm, but does
not establish standby power or battery-life improvement. USB remained connected.
System sleep targets stay masked because the sensor daemon's private wakelock
shim depends on that restriction.

## Source validation

`python3 scripts/ci/check-source.py` passes 64 source/regression tests and 4 flash
safety tests. A full ARM64 kernel Image links, both revised modules compile
against its output, and a staged depmod/modinfo check identifies CPU idle as
built in. No new full root filesystem image was built or published.
