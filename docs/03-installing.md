# Install a mobile image

For the **Exynos Galaxy S9+ SM-G965F (star2lte)**, with an unlocked bootloader
and working TWRP already installed. These instructions start from TWRP; they do
not cover bootloader unlocking or installing recovery.

Flashing USERDATA replaces the installed operating system and its user data.
RECOVERY, bootloader, modem, VENDOR and EFS are not written by these helpers.

## Download one bundle

Open [Mobile images](https://github.com/moooozi/galaxy-s9plus-mainline-linux/actions/workflows/mobile-images.yml),
select a successful run, then download one artifact:

| Artifact | User interface |
| --- | --- |
| `s9plus-kde-mobile` | KDE Plasma Mobile, using Ubuntu packages |
| `s9plus-gnome-mobile` | GNOME Mobile: matching mobile Shell, Mutter and Settings Daemon builds |

Each bundle contains `boot-s9plus.img`, `s9plus-rootfs.img.zst`, `SHA256SUMS`,
package/kernel manifests and these instructions. The GNOME bundle also records
its mobile source commits. These are separate images; the old combined
Plasma + GNOME Desktop image is a historical build.

Use BOOT and rootfs **from the same bundle**. The rootfs carries modules for
that exact kernel. A newer build may use a newer 7.3.x patch release.
The first workflow run must succeed before these download artifacts exist.
A generated image still needs device testing; CI cannot exercise this phone's
panel, GPU, audio or Bluetooth hardware.

## Verify and flash

On a Linux host with Python 3, `adb`, `unzip` and `zstd` installed:

```bash
git clone https://github.com/moooozi/galaxy-s9plus-mainline-linux.git
cd galaxy-s9plus-mainline-linux

# Example: use the KDE artifact. Substitute gnome-mobile for the GNOME bundle.
mkdir -p dist/kde-mobile
unzip ~/Downloads/s9plus-kde-mobile.zip -d dist/kde-mobile
(cd dist/kde-mobile && sha256sum -c SHA256SUMS && zstd -d s9plus-rootfs.img.zst)
```

Boot the phone into its existing TWRP and connect USB. Confirm that `adb`
shows the intended phone in recovery, then use its serial explicitly:

```bash
adb devices -l
export S9PLUS_SERIAL='<serial shown by adb>'

# TWRP may mount USERDATA automatically. Both aliases must be unmounted.
adb -s "$S9PLUS_SERIAL" shell 'twrp unmount /data; twrp unmount /sdcard'

# Write and verify USERDATA before changing BOOT.
python3 scripts/flash/flash_s9plus_rootfs_adb.py dist/kde-mobile/s9plus-rootfs.img

# Write the matching uniLoader BOOT image. This reboots after verification.
python3 scripts/flash/flash_s9plus_boot_adb.py dist/kde-mobile/boot-s9plus.img
```

The helpers verify star2lte identity, root recovery access, exact partition
mapping and capacity. Rootfs writes are resumable and checksum-verified per
chunk and in full, followed by a filesystem check. BOOT is read back in full
before rebooting. If the rootfs helper reports mounted USERDATA, inspect and
unmount the remaining TWRP mounts before retrying; do not bypass the check.
Do not flash a raw kernel Image or a raw `m71-*/boot.img` in place of uniLoader.

## First boot

The root filesystem expands to fill USERDATA, new SSH host keys are generated,
and the selected mobile interface logs in automatically. KDE uses SDDM;
GNOME Mobile uses GDM. Initial display scale is 3 on the 1440x2960 panel.
GNOME Mobile gets handset chassis identification and its built-in mobile
keyboard; KDE gets Plasma Keyboard and the settings launchers/dependencies.

The published development images use **user `ubuntu`, password `changeme`**.
Change it with `passwd` after installation. Root login is locked; use `sudo`.
Local builds can supply `IMAGE_PASSWORD`, `IMAGE_USER` and the common image
settings instead. Public workflows contain no personal credentials or SSH keys.

USB networking exposes the phone at `172.16.42.2`. Configure the host's USB
network adapter as `172.16.42.1/24`, then:

```bash
ssh ubuntu@172.16.42.2
```

For internet over USB, enable connection sharing on that host adapter; merely
assigning an address does not provide routing or DNS. A reinstall changes the
phone's SSH host key. Verify it through the physical device/serial console
before replacing the old entry. The cable also exposes a `ttyGS0` serial login.
Wi-Fi can be configured through the selected shell's network settings.

## Speaker firmware and Bluetooth identity

Both images include the matching experimental speaker/Bluetooth modules,
services and protected PipeWire speaker output. The public images do not carry
this owner's audio firmware or Bluetooth address.

For speaker playback, supply `calliope_sram.bin`, `calliope_dram.bin` and
`calliope_iva.bin` from **your phone's VENDOR partition** under
`/usr/lib/firmware/`. You can copy them out from an existing installation or
locate them in TWRP with VENDOR mounted read-only. Do not format VENDOR.
Then run `sudo systemctl start s9plus-audio.service` and reboot to initialize
the desktop audio graph. The protected `s9plus-speaker` output is the default;
retain its high-pass filter, crossover, limiter and conservative driver gains.

For Bluetooth, write **your phone's own EFS Bluetooth address**, in colon-separated
hex format, to `/var/lib/s9plus-bluetooth/bt_addr`. Keep its directory mode 0700,
file mode 0600 and ownership root:root. Then reboot. The board firmware symlink
and service ordering are already configured. Do not copy another device's address
or unload/re-register the board UART within the same boot.

Services skip automatic initialization while the required owner-supplied files
are absent. Failed initialization leaves a `loading` marker under the service's
`/var/lib/s9plus-*` directory. Inspect the logs before clearing it; this prevents
repeated probing after a crash. Detailed provenance and limits:
[Audio](https://github.com/moooozi/galaxy-s9plus-mainline-linux/tree/main/experiments/audio),
[Bluetooth](https://github.com/moooozi/galaxy-s9plus-mainline-linux/tree/main/experiments/bluetooth).

## Recovery and limits

If the new system does not boot, return to the existing TWRP and flash a saved
working **uniLoader** BOOT/rootfs pair. Keep RECOVERY available throughout.
The port's watchdog may return a failed warm boot to TWRP; inspect pstore and
serial logs before repeating the flash. For a kernel-only rollback, keep the
old kernel's matching modules in the rootfs.

Suspend, cameras, cellular/call audio, microphones and headphones are not
established by these builds. Experimental speaker playback and Bluetooth
controller/discovery were tested on the development phone; Bluetooth pairing
and audio streaming still need verification. Sporadic Panfrost faults also
remain. GNOME Mobile and the new SDDM image need their own visual/input testing;
a successful workflow is not a device-validation result.
