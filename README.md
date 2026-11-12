# Linux on the Galaxy S9+

Development now targets Debian and postmarketOS, with full and embedding kernel
variants and a separate kernel package repository. See the
[November 12 plan](docs/new-plan.md). Driver integration and hardware testing
come first; the new images and external repository are not implemented yet.

The Ubuntu installation and build instructions below remain a reference for
the existing hardware test system. Ubuntu image builds are now manual only.

[![checks](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/build.yml/badge.svg)](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/build.yml)
[![Mobile images](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/mobile-images.yml/badge.svg)](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/mobile-images.yml)

Ubuntu 26.10 ARM64 on the **Exynos Samsung Galaxy S9+ SM-G965F (star2lte)**,
with mainline Linux and uniLoader. Snapdragon models are unsupported.

The image pipeline builds two separate variants:

| Image artifact | Interface |
| --- | --- |
| `s9plus-kde-mobile` | KDE Plasma Mobile, with settings launchers, network/Bluetooth integration, Plasma Keyboard and basic KDE apps |
| `s9plus-gnome-mobile` | Actual GNOME Mobile: matching patched Shell, Mutter and Settings Daemon, with GNOME apps |

These replace the earlier combined image, which contained Plasma Mobile and
**desktop GNOME**. KDE uses SDDM; GNOME Mobile uses GDM. The new GNOME image is
not stock desktop GNOME with a mobile theme.

## Build and download

Run [Mobile images](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/mobile-images.yml)
manually in Actions. Each successful image job uploads a bundle
containing a compressed rootfs, matching uniLoader BOOT, checksums, package/kernel
manifests and install instructions. Artifacts are retained for 30 days.
No GitHub Release is created automatically. New workflows must be pushed and
complete successfully before downloadable images exist.

The kernel tracks the **newest supported 7.3.x patch at build time**, with no
patch pin. The exact selected tag and commit are recorded once per build.
Every required FUSE, speaker and Bluetooth module is rebuilt for that kernel.
Release candidates, EOL releases and silent minor-version fallbacks are excluded.

GNOME Mobile compiles in a separate reusable workflow in this repository,
natively on GitHub ARM64 runners inside the target Ubuntu 26.10 userspace.
The image assembly job installs its checked Debian package artifact. KDE uses
Ubuntu's packages and does not depend on the GNOME build succeeding.
[Build placement decision and pipeline details](docs/08-image-pipelines.md).

## Install

Start with an unlocked bootloader and working TWRP already installed.
Download one image bundle and follow [the installation instructions](docs/03-installing.md).
They cover checksum verification, unmounting USERDATA, verified rootfs/BOOT
flashing and first boot; bootloader unlocking and TWRP installation are excluded.

Installing the rootfs replaces the operating system and user data on USERDATA.
The flash helpers preserve RECOVERY, EFS, modem, VENDOR and bootloader partitions.
Use the BOOT and rootfs from the same bundle so the modules match the kernel.

Development images use **`ubuntu` / `changeme`**; change the password after
installation. USB networking exposes the phone at `172.16.42.2`, with the host
at `172.16.42.1/24`. The rootfs expands on first boot and generates unique SSH
host keys. Each variant starts its selected mobile shell automatically.

## Verified hardware and remaining work

On the development SM-G965F, **Linux 7.3.1-s9plus booted successfully** with all
eight CPU cores, SSH, Plasma Wayland with Panfrost hardware compositing, FUSE
portals, automatic speaker-driver loading and Bluetooth controller startup.
Real panel sleep and corner-mask restoration are retained. The new standalone
image variants, SDDM configuration and GNOME Mobile session still need their own
physical-device tests; a successful build is not a hardware-validation result.

The port provides internal UFS storage, native display/touch, Wi-Fi, USB network
and serial console, battery/charging and CPU/GPU frequency control. The panel
is 1440x2960 at approximately 60 Hz; images initialize scale 3.

Experimental speaker playback and Bluetooth discovery were confirmed on the
installed system. Audio firmware and the Bluetooth address must come from the
owner's phone; see [provisioning](docs/03-installing.md#speaker-firmware-and-bluetooth-identity).
Microphones, headphones, call audio, cellular, cameras and suspend remain
unsupported or unverified. Bluetooth pairing/streaming, longer speaker testing,
sporadic Panfrost faults and warm-reboot reliability remain open.

## Source builds and reference

- [Image pipelines and local build entry points](docs/08-image-pipelines.md)
- [Single-shell image builder](image/mobile/README.md)
- [GNOME Mobile package sources](image/gnome-mobile/README.md)
- [Earlier kernel and Ubuntu 24.04 build procedure](docs/02-building.md)
- [Hardware](docs/01-hardware.md), [drivers](docs/04-drivers.md), [validation](docs/07-validation.md)
- [Panel sleep/wake repair](docs/panel-sleep-wake.md), [preserved fixes](docs/local-fixes.md)
- [Speaker support](experiments/audio/README.md), [Bluetooth support](experiments/bluetooth/README.md)

`src/` contains the port drivers and tested kernel configuration;
`bootloader/uniLoader/` wraps the kernel for Samsung's boot chain;
`device/` supplies phone configuration; `image/` builds root filesystems;
`scripts/flash/` contains verified TWRP/ADB flash helpers. `dist/` and `.build/`
are ignored local outputs. Optional tools remain under `extras/`.

Based on [SheroAbi's port](https://github.com/SheroAbi/galaxy-s9plus-mainline-linux)
and [uniLoader](https://github.com/ivoszbg/uniLoader), with the GNOME Mobile and
ztOS sources credited in their manifests. GPL-2.0-only for this port's kernel
code; third-party components retain their licenses. See [LICENSE](LICENSE) and
[THIRD-PARTY.md](THIRD-PARTY.md).
