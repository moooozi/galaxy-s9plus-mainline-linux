# GNOME Mobile package build

`sources.json` is the reviewed lock for matching mobile Shell, Mutter and
Settings Daemon source commits and their Ubuntu packaging versions.
`runtime-packages.txt` selects what goes into the GNOME image, excluding test
and development packages. Update the three components together.

The reusable `.github/workflows/gnome-mobile.yml` compiles natively for ARM64
inside Ubuntu 26.10 and uploads Debian packages plus corresponding sources and
checksums. The image job installs them through APT/dpkg and verifies the lock.
See [the architecture decision](../../docs/08-image-pipelines.md).

For a local packaging check on an x86-64 host, the build script also accepts
`GNOME_BUILD_ARCH=amd64` inside Ubuntu 26.10. That produces amd64 test artifacts,
which the ARM64 image installer rejects. It does not replace the ARM64 workflow.

The mobile Shell package adds runtime dependencies on the GnomeAutoar and
ModemManager typelibs. Desktop Ubuntu's packaging alone misses these imports:
one aborts Shell startup; the other breaks mobile quick settings. The image
validator loads these namespaces in GJS, rather than relying on `--version`.
Package revision `0s9plus2` includes this correction. The image also explicitly
installs accessibility, login-keyring and calendar backends when recommendations
are disabled.

On 2026-11-02, the ARM64 image booted on the development star2lte after these
missing packages were installed. GNOME Mobile 51.1.mobile.22, a Wayland session,
1440x2960 at scale 3 and Mali-G72/Panfrost acceleration were verified over SSH.
The owner confirmed GNOME was visible; touch and mobile keyboard behavior still need explicit confirmation.

Local patches under `patches/<component>/` apply with zero fuzz before packaging.
The reviewed mobile commits remain pinned; patches and corresponding sources
are included in the package provenance and package-cache key.

The phone power corrections cover three connected components:

- Shell monitors the public DisplayConfig DPMS property asynchronously, restores
  the unlock dialog's cancellation contract, and honors `lock-delay=0` on explicit
  activation without waiting for the idle fade. Accelerator signals snapshot
  the display state before the asynchronous activity wake.
- Settings Daemon handles press/release for `toggle-blank`: short release blanks
  or wakes, while a one-second hold requests the session's power confirmation
  dialog. Other power policies retain their existing behavior. Pending holds
  are cancelled on sleep, Shell replacement, and service shutdown.
- Mutter supports opt-in `MUTTER_TOUCHSCREEN_WAKEUP=double-tap`. Input remains
  enabled while the panel sleeps, and sleeping-screen touch contacts are consumed
  before idle tracking and client delivery. Only a completed, nearby double tap
  wakes the display; it never dismisses the password lock. The GNOME phone image
  opts in through a Shell user-service drop-in. This does not implement system
  suspend wake, which remains outside this port's verified support.

The recognizer tests cover ordinary taps, time/distance limits, swipes, multiple
contacts, cancellation, and timestamp wraparound. Native amd64 compilation checks
verify the patched Mutter library and Settings Daemon executable. ARM64 packages
and physical button/touch/authentication tests are still required before claiming
all phone power behaviors work.
