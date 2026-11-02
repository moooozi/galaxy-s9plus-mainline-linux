# Separate mobile images

Use `.github/workflows/mobile-images.yml` to generate installable KDE and GNOME
Mobile artifacts. These builders replace the combined-image approach for new
builds. Build architecture and source policy are in
[docs/08-image-pipelines.md](../../docs/08-image-pipelines.md); installation starts
from existing TWRP in [docs/03-installing.md](../../docs/03-installing.md).

`build.sh kde` or `build.sh gnome` runs as root inside native ARM64 Ubuntu 26.10,
with debootstrap, ubuntu-keyring, kmod, e2fsprogs, OpenSSL, Python and zstd.
Download the same-run `s9plus-kernel` artifact into `.build/inputs/kernel`;
GNOME also needs `gnome-mobile-packages` in `.build/inputs/gnome`. Use a fresh
work directory. `WORK`, `OUT`, `KERNEL_DIR` and `GNOME_DIR` can override paths.
Standard user/timezone/password settings come from `image/common/lib.sh`.
The public development-image password is `changeme`; local builds can override it.

No local `.build` kernel outputs, private password files, owner Bluetooth address
or pre-extracted audio firmware are needed. Both images include the new matching
modules; owner-specific provisioning is documented in the install instructions.
