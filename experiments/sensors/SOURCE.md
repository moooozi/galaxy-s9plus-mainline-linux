# Sensor source and changes

Upstream: [Zerone-Laboratories/ztOS](https://github.com/Zerone-Laboratories/ztOS/tree/7f42ddc3ba468e4e21c7145cbb973f5aa57d5358),
commit `7f42ddc3ba468e4e21c7145cbb973f5aa57d5358`.
`upstream.json` records original paths and SHA256 hashes before adaptation.

The transport in `driver/` is Broadcom/Samsung GPL-2.0 vendor code adapted by
ztOS for mainline. Original notices are retained. The `q_os` header contains an embedded Broadcom sensor firmware patch from
the vendor kernel, matching ztOS's tested implementation. The unused P patch
is not vendored. This is a firmware payload, not firmware authored by this port. The proprietary
`lhd` executable and Android runtime are not bundled: they must come from the
owner's existing SYSTEM/VENDOR partitions. No EFS or RADIO access is required.

Local changes:

- Restrict board probing to `samsung,star2lte`; clear readiness and queued SSP
  packets before a reset, and invalidate readiness on a reported hub reset.
  Guard failed-probe cleanup and adapt timer callback signatures explicitly
  instead of casting incompatible function pointers.
- Correct SSP write accounting to exclude BBD's private two-byte header, and
  bound payloads to its 1022-byte capacity. At shutdown, stop SPI work before
  parking the hub signals and disabling only its dedicated LDO37 supply. This
  passed automatic firmware loading after an initial normal Ubuntu reboot,
  but a later reboot failed ROM synchronization again. A November 12 test with
  the supported supply-cut reset also failed before explicit output-low parking.
  A high MCU_RESP level is no longer treated as a reset failure or a reason for
  repeated holds, because successful firmware boots show the same level.
- `s9plus-sensor-iio.c` is a new GPL-2.0 bridge. A single root writer publishes
  decoded samples. IIO devices appear on first data and disappear on writer
  close. Accelerometer units use the upstream documented 4096 counts/g; gyro
  scale and device mount orientation still need physical verification.
- `ssp.py` implements the protocol documented/implemented in `zrn-ssp.py` and
  `ztoscsf-sensord.c`: serialized header/echo/payload, fragmented packet and
  stream handling, timestamps and strict frame bounds. This derivative and
  the firmware supervision/mount helpers use GPL-3.0-only, consistent with the
  upstream repository's general licence. No ztMETRO brightness policy is used.
  Captured owner-firmware frames require 32-bit gyro axes, while accelerometer
  axes remain 16-bit. A captured-frame test guards this distinction. A device
  udev mount matrix adapts the accelerometer to the phone display coordinates.
- The Android root uses private mount propagation for /dev and read-only,
  no-journal-replay partition mounts. Runtime APEX layouts are checked rather
  than assuming one Android version. Firmware startup has a deadline and no
  automatic restart loop; a persistent marker blocks another load after a fault.
- `compat/wakelock-no-suspend.c` is a new dependency-free GPL-2.0 preload for
  lhd's two legacy wakelock calls. The installed modern libhardware_legacy would
  otherwise wait for an absent Android system-suspend service. Vendor libraries
  are selected first; the shim is private to the chroot and requires masked
  system-sleep targets. On-phone tracing confirmed that this lets lhd reach
  firmware downloading. ROM synchronization depends on the board reset sequence described below.

The runtime and module trial results, including the observed failures and subsequent reboot tests, are recorded in [README.md](README.md).

November 12 reset hardening: recovery pinctrl shows SCK/MOSI pulls disabled.
The parking path now explicitly drives those AP output pins low, keeps MISO
an input, and preserves unrelated mux fields. The dedicated LDO37-off error
is propagated. The revised transport passed two consecutive normal reboots
after a TWRP recovery passage, with automatic firmware loading and live samples.
