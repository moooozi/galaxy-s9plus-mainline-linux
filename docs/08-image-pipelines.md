# Mobile image pipelines and GNOME build placement

The default pipeline produces **two Ubuntu 26.10 ARM64 images**: KDE Plasma
Mobile and GNOME Mobile. The historical `image/ubuntu-26.10` builder preserves
the previously installed combined image; new workflows use `image/mobile`.

## Build GNOME in this repository, as a separate reusable workflow

GNOME Mobile needs matching patched **Shell, Mutter and Settings Daemon**.
The reviewed Shell source requires its exact Mutter version; Settings Daemon
provides the mobile power-button behavior. Installing stock GNOME, adding a
theme or building Shell alone is insufficient.

`gnome-mobile.yml` builds a coherent set of native ARM64 Debian packages inside
Ubuntu 26.10 on a GitHub ARM64 runner. Ubuntu provides the rest of the userspace.
The image job consumes the resulting artifact and installs only runtime packages.
This separates compilation from image assembly without needing another repo.

| Approach | Benefits | Costs | Decision |
| --- | --- | --- | --- |
| Compile GNOME inside the rootfs assembly step | One job | Repeats expensive builds; development dependencies can leak into images; harder to isolate failures | Avoid |
| Separate reusable package workflow here | Independent logs/cache; atomic source changes; same-run artifacts; KDE can finish if GNOME fails | Maintain packaging here | Use now |
| Separate repo publishing packages/releases | Useful for several devices/distros and an independent desktop release cadence | Cross-repo version/auth/retention coordination; a second release process; ideally an APT repository for updates | Extract when there are other consumers |

A reusable workflow is a separate build stage, not a build on the phone.
GitHub [provides native ARM64 runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The runner's Ubuntu 24.04 host executes an ARM64 Ubuntu 26.10 container, so the
packages match the target userspace without QEMU compilation. Kernel compilation
uses an x86-64 cross-toolchain; rootfs assembly is native ARM64 too.

## Source and package boundaries

`image/gnome-mobile/sources.json` records reviewed Git commits, the matching
GNOME version, and exact Ubuntu source-packaging versions. Source export
normalizes text line endings and includes pinned subprojects such as GVC and
GVDB. Meson is forbidden from implicitly downloading dependencies.

The builder combines each mobile tree with the reviewed Ubuntu Debian package
split and dependencies, omitting Ubuntu's stock-GNOME quilt patches. It builds
in order: Settings Daemon, Mutter, Shell. Ubuntu packaging changes or missing
files stop the build. The reviewed mobile ABI baseline explicitly omits eight
desktop-only or replaced symbols, recorded with reasons in
`image/gnome-mobile/mutter-symbol-removals.json`. All other missing symbols still
fail; new symbols are allowed. This Mutter is for the matching mobile Shell,
not an ABI-compatible replacement for arbitrary desktop Mutter consumers.
The artifact contains `.deb`s, corresponding source archives, `.buildinfo`,
`.changes`, source/build manifests and SHA256 checksums. The image installs the
runtime subset through APT/dpkg, verifies exact versions, and holds the stack
together. No raw `meson install` overwrites package-owned image files.

The default source lock is GNOME Mobile 51.1.mobile.22:
[Shell](https://gitlab.gnome.org/verdre/gnome-shell-mobile/-/tree/c602286053f9e06b3493decb4a9dabe8ba20ad9c),
[Mutter](https://gitlab.gnome.org/verdre/mutter-mobile/-/tree/7e7b25f68c7719ebf3b651808824e0c8bd33020d),
[Settings Daemon](https://gitlab.gnome.org/verdre/gnome-settings-daemon-mobile/-/tree/bbb6997c79ce8dce5eb17fe4d93ab6b77dad5e93).
Updating this stack means reviewing all three and changing the lock together.
Held packages will not receive stock Ubuntu GNOME replacements automatically;
rebuild/reinstall the matching package set to update them.

Complete successful package builds are cached by source/packaging/build-script
hash. `rebuild_gnome` forces a rebuild against current target dependencies.
It is also available on the standalone GNOME package workflow. Cached builds
are checksum-verified before use. Ubuntu's package archives are not snapshotted:
these builds record their inputs but do not promise bit-for-bit reproduction.
If an exact packaging version disappears, update it through review rather than
falling back to unrelated source versions or an unverified download.

## Kernel policy: latest supported 7.3.x, no patch pin

`kernel-source.json` fixes the **series**, not the patch. At the start of each
kernel build, `resolve-kernel.py` reads kernel.org's
[release metadata](https://www.kernel.org/releases.json), selects the newest
non-EOL stable release in 7.3.x, and resolves its stable Git tag to an exact
commit. All following jobs use that single resolved manifest. No RC, master,
older-series fallback or automatic minor-series upgrade is allowed. If 7.3 is
EOL, the workflow stops so the next series can be reviewed.

The known-good starting config is the 7.3.1 configuration that booted the
SM-G965F on 2026-11-02. Later patch releases run `olddefconfig`, apply the same
board patches and rebuild every required module. Upstream charger-driver drift
or incompatible patch anchors stop the build rather than silently dropping
board fixes. BOOT and modules are version-coupled in the artifact manifest.

The pipeline builds uniLoader from source, using the checksum-verified official
TWRP 3.3.1-0 image only as an outer-header template. It never installs that
recovery image. The kernel artifact includes its corresponding source tree,
configuration, module manifest, boot image and checksums.
The initramfs BusyBox download verifies Ubuntu's InRelease signature, the index
hash and size, the package hash, and its static ARM64 ELF format.

## Images and execution

`mobile-images.yml` starts the kernel and GNOME package workflows independently.
KDE needs only the kernel artifact; GNOME needs both. `mobile-rootfs.yml` is the
shared image-assembly workflow. It runs on changes to image/kernel/build inputs
on main, or manually from the Actions page. Pull requests run syntax/regression
checks and workflow lint without publishing images. Artifacts expire after
30 days; no GitHub Release is automatically created.

Both variants share `common-packages.txt`: networking/SSH, PipeWire/Bluetooth
integration, firmware-dependent hardware support, a terminal editor and system
tools, Firefox from Mozilla's signed DEB repository, fonts and portal support.
Kernel FUSE is included for the document portal. Device voltage, display,
watchdog, USB, storage and no-suspend settings are retained.

KDE adds `plasma-mobile-core`, `kde-cli-tools`, hfd-service, KIO extras,
ksystemstats, bluedevil, kscreen, Plasma Settings, networking and Polkit agents,
Plasma Keyboard and basic KDE apps. The two outdated quick-setting module
links are repaired idempotently. SDDM avoids pulling GNOME Shell into this image;
the packaged direct-login Plasma service is disabled to avoid seat conflicts.

GNOME uses GDM with `FallbackSession=gnome`, the patched stack, handset chassis
metadata, the built-in mobile keyboard, GNOME settings/apps and its portal.
No Plasma shell is installed. Both variants initialize scale 3 once per user.

Before imaging, the builder checks package audits, UI/session separation,
quick-setting launchers, mobile GNOME schemas/version, FUSE/module releases,
service configuration, root/SSH policy, merged-/usr and device workarounds.
The filesystem is checked and compressed with zstd. Each downloadable image
bundle includes a matching BOOT, rootfs, manifests, install instructions and
checksums. Installation starts from an already working TWRP:
[03-installing.md](03-installing.md).

Local validation on 2026-11-02 built the selected 7.3.1 kernel, all 23 modules,
DTB and uniLoader BOOT through the new scripts; artifact checksums and source
archive checks passed. The GNOME stack compiled and installed in a native
Ubuntu 26.10 amd64 validation container, with exact package versions, mobile
schemas and dynamic linking checked. This validates packaging on amd64, not
an ARM64 image or a graphical session. Eighteen source/regression checks pass.

CI does not prove physical input, panel, GPU stability or Bluetooth/audio
behavior. Display/TTY-dependent upstream GNOME integration tests are skipped
in the package container; test binaries are still packaged. Device tests remain
necessary before labeling a new image as hardware-validated. The currently
installed phone is not changed by building these workflows.
