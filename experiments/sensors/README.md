# Galaxy S9+ sensor port

**November 12 validation:** kernel #8 recovered firmware loading and live IIO
samples after a TWRP passage. The revised transport then passed two consecutive
normal reboots with automatic sensor firmware loading and light/motion samples.
The CPU-idle guard remains enabled alongside sensors. Physical orientation
calibration and automatic brightness behavior still await confirmation.

Recovery pinctrl showed that SCK/MOSI have no pull-downs. The parking path now
explicitly drives those AP output lines low, keeps MISO an input and preserves
unrelated mux fields. A failed dedicated LDO37-off operation is reported.
Host pin-state regressions and module compilation pass; these two warm reboots
validate the observed sequence, not every future hardware/firmware condition.

Before that change, a November 4 boot and bounded November 12 trials failed
ROM synchronization and left durable markers. A supply-cut-only trial also
failed. Their logs and guard backups remain in the local session artifacts and
`/var/lib/s9plus-hardware-trial/sensor-recovery-20261112/`. Markers were archived
deliberately for each new controlled trial, never cleared automatically.

`MCU_RESP` is a handshake level, not proof of reset completion: successful boots
also show it high after reset. The source performs one bounded hold instead of
using that level to repeat increasingly long power cycles. System sleep remains
masked, transport modules were not unloaded during testing, and the source
retains the persistent failed-initialization guard.

Earlier bring-up on the SM-G965F with `7.3.1-s9plus` succeeded after passing
through TWRP: the owner's vendor daemon loaded the hub firmware and the reader
published live light, accelerometer and gyro samples through IIO. SensorProxy
detected acceleration and light; GNOME managed panel orientation and the user
observed rotation. Final device mount calibration still awaits physical feedback.
Automatic brightness behavior has not been physically verified.

Access was recovered over Wi-Fi at `192.168.178.172`, using the existing pinned
SSH host key. Missing USB enumeration did not mean the phone was disconnected.
A normal reboot, the documented sensor-only supply reset, a slower CMU divider
and a 26 MHz oscillator-parent trial all retained the ROM handshake failure.
Trial clock settings were restored. USB data now works. Two recovery passages
allowed firmware initialization; an intervening normal reboot reproduced the
ROM handshake failure. The installed shutdown fix parks the hub's signals and
switches off its dedicated LDO37 supply after SPI stops. Normal reboot then
passed automatic firmware loading and live sensor publication. The firmware
service also explicitly waits for SYSTEM/VENDOR device links before mounting.
The sensor reader is enabled on the phone and in future-image recipes, but
its dependency guard prevents startup after the recorded firmware failure.

The port includes BCM4773 transport, bounded supervision of the owner's vendor
`lhd`, and light/accelerometer/gyro publication as real kernel IIO devices.
Ubuntu's existing `iio-sensor-proxy` consumes light and acceleration through
standard polling backends. No custom GNOME brightness or rotation daemon is
installed. Gyro raw counts are exposed for diagnostics; scale is not yet known.
Other hub sensors, GNSS, full suspend and CPU hotplug are outside this change.

The S9+ vendor DT wiring matches the upstream transport: SPI `0x13ac0000`,
gph0-0/1/2/3 for clock/data/chip-select, gpa1-7 host request, gph0-5 request,
gph0-4 response, gpg0-2 power enable, gpa0-5 AP_SLEEP, gpa4-0 hub interrupt,
S2MPS18 LDO37. Source provenance: [SOURCE.md](SOURCE.md).

## Build

In the existing build container, prepare an isolated copy of the running
kernel's source and output (including `.config`, `Module.symvers`, `vmlinux.o`
and generated headers). Then:

```sh
KERNEL_SRC=/work/.build/sensors-idle/src \
  bash /work/experiments/sensors/build-modules.sh
```

The script adds `CONFIG_IIO=m` to that isolated build, compiles
`industrialio.ko`, `zrn-bbd.ko`, `s9plus-sensor-iio.ko`, and the conservative
CPU idle module, and records hashes. Local compilation against the exact kernel
completed without unresolved symbols. IIO core has no module dependencies in
this build. All four modules loaded into the unchanged running kernel. No BOOT
write is needed for this module-only trial.

Future mobile image builds include the sources, modules, compatibility library,
mount matrix and enabled sensor reader. Its firmware service is pulled in by
the reader and retains the persistent failed-initialization guard.

The installed Android 16 runtime initially selected incompatible system
libraries; vendor-first `LD_LIBRARY_PATH` fixes that selection. Its current
`libhardware_legacy` waits for Android's system-suspend service. A dependency-free
ARM64 preload implements only `acquire_wake_lock`/`release_wake_lock` inside lhd's
private chroot. The supervisor refuses to use it unless all system sleep targets
are masked. No host-wide library replacement is installed. This fixed userspace
startup. Passing through the vendor recovery subsequently allowed SPI ROM
synchronization. The SSP bridge now excludes BBD's private length header from
write return counts and bounds payloads to its actual packet capacity. Captured
phone frames established that this firmware's gyro axes are signed 32-bit,
while acceleration uses signed 16-bit axes; the parser handles both layouts.

## First phone test

Install matching modules under `/usr/lib/modules/$(uname -r)/extra/` and run
`depmod -a`. Copy the rootfs overlay preserving merged-/usr directory symlinks.
Keep USB SSH connected, GNOME running, and the existing recovery/BOOT backups.
Read-only mount checks must establish that SYSTEM and VENDOR are still intact;
an incompatible Android runtime is a firmware-service failure, not sensor data.

```sh
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl start s9plus-sensors.service
sudo journalctl -u s9plus-sensorhub -u s9plus-sensors --no-pager
cat /run/s9plus-sensorhub/samples.json
grep -H . /sys/bus/iio/devices/iio:device*/name
monitor-sensor
```

Cover/uncover the light sensor and move/rotate the phone. Verify live light
changes and approximately 4096 acceleration counts at rest, then check the
orientation convention before accepting GNOME rotation. Confirm the standard
SensorProxy `HasAmbientLight`, `HasAccelerometer` and reported changes. Test
service stop/start and one reboot before persistent activation. Never claim
battery savings without a separate whole-device measurement.

`s9plus-sensorhub.service` leaves `/var/lib/s9plus-sensorhub/loading` if startup
fails. Inspect logs before manually clearing it. No automatic retry resets the
hub. `s9plus-sensors.disable` under `/etc` prevents future service startup.
Stopping `s9plus-sensors` closes the IIO bridge and removes published devices;
stopping `s9plus-sensorhub` terminates its vendor process. Do not unload the
transport to experiment with a replacement module; reboot instead.
