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
