# Galaxy S9+ charger boot and charging userspace

This implementation selects charging userspace using Samsung's actual boot
reason. After powering down and reconnecting the charger, the owner confirmed
the real charging path worked. This follows separate manual-screen tests and
normal-reboot checks.

## Boot selection

uniLoader saves S-Boot's incoming x0 address in the mainline DT's
`/chosen/s9plus,sboot-fdt-address`. It does not parse or copy vendor boot data.
The board DT reserves 2 MiB of no-map memory at 0x8a000000, where this phone's
S-Boot supplies its FDT, so the Linux allocator cannot overwrite it.

Before systemd chooses a default target, `s9plus-charging-generator` validates
that the pointer matches the exact reserved region. It maps /dev/mem read-only
and reads naturally aligned 32-bit words. Bulk copies from device-mapped memory
fault on this platform; pread and Python mmap slicing must not be used here.
The parser checks header, block bounds, nodes, property bounds and termination,
and accepts only an unambiguous complete `androidboot.mode=charger` token.

For charger boots the generator overrides default.target in
/run/systemd/generator.early, selecting `s9plus-offline-charging.target` before
GNOME is started. The persistent default stays graphical.target. Normal,
missing or malformed vendor data selects the ordinary desktop. An owner can
create `/etc/s9plus-charging.disable` to disable automatic selection. Boot mode
and a concise error, if any, are recorded in
`/run/s9plus-charging/boot-mode.json`; vendor boot arguments are not logged.

`/etc/s9plus-charging.debug-usb` adds USB gadget, NetworkManager, SSH and user
login services to the charging target for phone testing. It is not included in
the image overlay. Without it the charging boot needs only basic initialization,
the existing charger input-limit service and the screen controller.

## Charging target

The fbdev controller activates virtual terminal 1, waits for it to become active,
and enters graphics mode. It saves and restores the previous VT. It shows the
fuel-gauge percentage, blanks after 12 seconds, and wakes on a short Power press.
An exclusive input grab keeps logind from acting on that same press.

Holding Power for 2 seconds starts graphical.target and display-manager.service.
The charging target and controller stop through systemd conflicts and PartOf;
KillMode=mixed lets the child systemctl finish acknowledging that transition.
The full desktop services start without another reboot. Ten continuous seconds
of confirmed USB absence request an orderly systemd power-off. Missing supply
reads never count as a disconnect or as 0/100% capacity.

Manual entry remains useful for testing:

```sh
sudo systemctl start s9plus-offline-charging.target
```

This is running Linux with reduced userspace, not an electrically powered-off
application processor. It does not enable suspend or change current/voltage
limits. The vendor battery state machine is not reproduced here. Net charge
current and autonomous full-charge termination need independent verification;
see [charging.md](charging.md).

## Validation and rollback

The installation task's STATUS.md records actual phone results. Normal reboot
with address-preserving loader and reserved board DT passed. The fixed reader
returned the real normal boot mode, and a fresh reboot with it correctly started
GNOME with mode=normal/error=null. The owner subsequently confirmed the actual
power-off/cable-insertion test worked. A fresh SSH capture of that charger boot
was unavailable because USB was no longer connected to the computer. Prior
manual tests confirmed visible screen, blanking, Power wake, timer return and
an injected Power hold lasting 2.5 seconds returning to GDM without reboot. Source tests
cover invalid/truncated vendor data, complete mode tokens, reserved-address
checks, aligned reads, target generation, input policy and VT restoration.

An earlier candidate that parsed vendor memory inside uniLoader caused a boot
loop and was removed. Its archived diff is
`.build/offline-charging/failed-loader.patch`; do not reinstall that image.
Current address-only loader changes were tested separately before adding the
reservation and userspace reader.

Known-good rollback: host `dist/multires-local/boot-s9plus.img`, SHA256
`5bfad0cd7caa705806eaac17cdc51006e76d387b915a710cef5ddf96f541017b`.
The phone retains full BOOT backup
`/var/lib/s9plus-offline-charging/boot-before.img`. TWRP remains available.
Restoring original BOOT or creating the disable file selects normal Ubuntu.
