# Experimental Ubuntu 26.10 / Plasma Mobile image

This preserves the builder used for the verified installation. Plasma Mobile
is the default Wayland session; desktop GNOME remains an alternative. The
existing Ubuntu 24.04 builder is unchanged.

Run `bash image/ubuntu-26.10/build.sh` as root inside a privileged ARM64-capable
build container. Required tools include debootstrap with its generic Ubuntu
`resolute` script, the Ubuntu archive keyring, QEMU ARM64 binfmt configuration
at `/usr/lib/binfmt.d/qemu-aarch64.conf`, kmod, rsync, Python, OpenSSL and
e2fsprogs. Use a filesystem supporting capability xattrs.
Set the desired image password in `.build/initial-password` (mode 0600).
No password file is supplied in the repository.

The builder needs the exact existing kernel output in `.build/src/mainline/out`,
including `fs/fuse/fuse.ko`, modules.builtin and modules.builtin.modinfo.
Build FUSE with the original compiler/config using
`make O=out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j8 fs/fuse/fuse.ko`.
The module must match kernel release 7.1.0-dirty.

Rootless containers need recursive /dev binding with slave propagation so
APT's unprivileged signature checker can access /dev/null. GDM 51 requires
`FallbackSession=plasma-mobile`, without a .desktop suffix; normalize the
display-manager alias to gdm.service and disable Plasma's competing direct
TTY login service. The dconf empty string array is explicitly typed. FUSE
is installed and boot-loaded for the document portal. KDE gets initial scale
3 on DSI-1 and the packaged Plasma keyboard input method.

Stage markers under `.build/stonking-image-work` allow resuming interrupted
builds. Changes to completed stages require invalidating their markers and
all affected later stages. Output is `dist/stonking-mobile`. The helper never
flashes the phone. An existing final image is not automatically regenerated.
Audio and Bluetooth additions under experiments are installed separately;
the verified reusable rootfs predates those additions.

Original installed system: GNOME Shell 51.0, Plasma Mobile 6.7.5, Panfrost
hardware compositing, 1440x2960 at approximately 60 Hz and scale 3.

The separate plasma-completion stage installs the previously omitted recommended
packages, including kde-cli-tools (`plasma-open-settings`), plasma-mobile-core,
hfd-service, kio-extras and ksystemstats. It runs even when the initial Plasma
package stage is already complete and invalidates final cleanup/image markers.
The installed phone's package audit was clean and Wi-Fi settings launched after
these additions; this does not establish haptic or cellular hardware support.
