# Debian and postmarketOS images

The new build workflow is `distribution-images.yml`. It assembles three images
from signed package repositories; it does not compile a kernel:

| Image | Distribution | Desktop | Kernel |
| --- | --- | --- | --- |
| `debian-embedding` | Debian 13 (trixie) | None | embedding |
| `postmarketos-plasma` | postmarketOS v26.06 / Alpine v3.24 | Plasma Mobile | full |
| `postmarketos-phosh` | postmarketOS v26.06 / Alpine v3.24 | Phosh | full |

Kernel ownership/release CI is in
[moooozi/galaxy-s9plus-kernel](https://github.com/moooozi/galaxy-s9plus-kernel).
Both distributions configure its package repository with pinned public keys.
Normal system updates install new kernel packages and a matching BOOT; reboot
when ready. The kernel repository owns driver sources and the matching runtime
helpers. Older Ubuntu recipes remain historical/manual and are not used by the
new workflow. The installed Ubuntu phone remains the hardware validation system.

## First access

Debian starts `sshd`, uses DHCP on LAN connections and advertises `s9plus.local`
via mDNS. Wi-Fi needs network credentials; it cannot join an unknown WLAN by
DHCP alone. USB NCM provides networking and a serial console. The USB connection
requests DHCP and also has `172.16.42.2/24`; the existing host sharing profile
uses `172.16.42.1/24`. Other hosts can configure that address or share their
connection. On networks without mDNS, find the DHCP lease in the router.

An unconfigured Debian image uses **`debian` / `debian`**, requires a password
change on first login, and permits no root SSH login. For the initial SSH
password change use an interactive terminal (`ssh -t debian@s9plus.local`).
USB serial is another initial-login route. The postmarketOS desktops use
**`user` / `147147`**, with the normal greeter; change that password after login.
All images generate unique SSH host keys and machine IDs on the phone.
No reverse SSH tunnel is configured: the requirement is an SSH server.

Prefer configuring a user/public key before flashing. Decompress the rootfs,
then run:

```
zstd -d s9plus-rootfs.img.zst
python3 scripts/images/configure-image.py s9plus-rootfs.img \
  --user alice --ssh-public-key ~/.ssh/id_ed25519.pub
```

Repeat `--ssh-public-key` for multiple keys. Keys are validated with ssh-keygen.
Supplying keys without a password selects key-only SSH authentication. An
optional `--password-file /private/path/password.txt` stores a SHA512 password
hash, never the plaintext password; use it if password login is also wanted.
The file `/etc/s9plus/first-boot.json` is applied once, before SSH/the greeter,
and removed after successful setup. Preconfiguration changes the image checksum:
regenerate SHA256SUMS before using the existing flash helper. These commands
modify only a regular ext4 image file, not the connected phone.

## Battery policy

Embedding defaults to stop 65% / resume 63%. Full defaults to no added limit
(stop 100%). Both provide configurable, persistent preservation:

```
sudo s9plus-battery-preservation --stop 80 --start 78
sudo s9plus-battery-preservation --stop 65
sudo s9plus-battery-preservation --stop 100
```

Saved settings survive reboot and package updates. The kernel also exposes the
standard power-supply threshold attributes. No desktop settings panel is added
by this change; the command is available in either desktop's terminal. Firmware
charge termination and thermal protection remain separate from this polling
policy; fast charging is not enabled by these images.

## Build/install boundaries

Kernel packages must be released and the signed Pages repository deployed
before dispatching image builds. The new workflow uses native ARM64 runners.
Each artifact contains compressed ext4 USERDATA, BOOT, kernel/package manifests,
installation notes and checksums. Use BOOT and USERDATA from the same artifact.
No build workflow flashes a connected phone.

Actual flashing replaces the selected device's installed system. Follow the
existing [installation procedure](03-installing.md) and its partition/hash
checks; retain recovery and backups. This migration has not authorized replacing
the current Ubuntu hardware test installation. New images require their own
boot/display/touch/network/charging trials; the November 12 Ubuntu driver results
do not validate Debian/postmarketOS desktop behavior.

The sensor runtime still requires the owner's existing SYSTEM/VENDOR contents;
audio firmware and Bluetooth identity are not embedded from the owner's phone.
Sleep targets remain masked because deeper CPU/system suspend is unvalidated and
the sensor shim requires that restriction. Removing DRM from embedding does not
prove that the S-Boot-initialized display is off or that standby improves.
