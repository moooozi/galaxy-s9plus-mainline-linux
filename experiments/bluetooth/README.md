# Experimental S9+ Bluetooth controller support

Verified on SM-G965F on 2026-11-02: firmware initialization, controller power,
BR/EDR and LE discovery, ten nearby devices, 3 Mbaud UART, and automatic startup
after reboot. Pairing, HID and Bluetooth audio streaming remain unverified.
Suspend remains disabled and the board driver uses sleep_hook=0.

Board driver and kernel patch adapted from Zerone-Laboratories/ztOS at
94b35c2a1f4ceb568bc0ab60f5a1acebe7cfefaf, `bluetooth/driver/zrn-bt.c`
and `bluetooth/patch-btbcm.py` (GPL-2.0). The patch adds star2lte to the
broken transmit-power-command quirk and the board-specific 3 Mbaud setting.
The local startup helper waits for firmware and management index re-registration
before notifying systemd, and uses the owner's EFS Bluetooth address.

## Build from the existing exact kernel

In the original GCC 13.3.0 cross-build container with this repository at /work:

```sh
cd /work
mkdir -p .build/bluetooth-work/src .build/bluetooth-work/driver
rsync -a --exclude=/out --exclude=/.git .build/src/mainline/ .build/bluetooth-work/src/
cp experiments/bluetooth/driver/Makefile experiments/bluetooth/driver/zrn-bt.c .build/bluetooth-work/driver/
python3 experiments/bluetooth/patch-btbcm-s9plus.py .build/bluetooth-work/src
bash experiments/bluetooth/build-modules.sh
```

Requires the original `.build/src/mainline/out` (including Module.symvers and
vmlinux.o). Fifteen matching modules are emitted in `.build/bluetooth-work/modules`.
Verify release/vermagic 7.1.0-dirty against the target before installing.
No upstream binaries or firmware are included.

## Install on the target

Install all fifteen modules under
`/usr/lib/modules/7.1.0-dirty/extra/s9plus-bluetooth/`, then run depmod.
Use the existing own-phone `brcm/bcm4361B2_semco.hcd` firmware and create
`/usr/lib/firmware/brcm/BCM.samsung,star2lte.hcd -> bcm4361B2_semco.hcd`.
Install Ubuntu bluez (btattach/btmgmt). Copy the rootfs overlay with root
ownership, retaining merged-/usr directory symlinks:

```sh
tar -C rootfs --owner=0 --group=0 -cf - . | tar -C / --keep-directory-symlink --no-same-owner --no-overwrite-dir -xpf -
install -d -m 700 /var/lib/s9plus-bluetooth
# Write this phone's own EFS Bluetooth address into bt_addr, then:
chmod 600 /var/lib/s9plus-bluetooth/bt_addr
systemctl daemon-reload
systemctl enable s9plus-bluetooth.service
```

Reboot to initialize; BlueZ is ordered after the controller service.
Never package directory entries for a top-level `lib/`: a prior transfer
replaced the target's /lib symlink and required recovery repair. Use usr/lib
paths and regular-file-only archives with numeric root ownership for modules.
Do not unload/re-register the board UART within one boot: samsung_tty retains
the old port. Reboot for reinitialization. A persistent `loading` marker blocks
repeated automatic attempts after failed initialization; inspect logs before
clearing it. The owner's address and firmware must be supplied separately.
