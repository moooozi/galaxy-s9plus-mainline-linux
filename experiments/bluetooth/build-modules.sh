#!/bin/bash
# Run in s9plus-ubuntu-build; source is copied separately, excluding out/.git.
set -euo pipefail
work=/work/.build/bluetooth-work
cd "$work/src"
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
out="$work/out"
mkdir -p "$out"
if [ ! -f "$out/.config" ]; then
    cp /work/.build/src/mainline/out/.config "$out/.config"
    scripts/config --file "$out/.config" -m BT -m BT_HCIUART \
      -e BT_HCIUART_H4 -e BT_HCIUART_BCM -m BT_RFCOMM -e BT_RFCOMM_TTY \
      -m BT_HIDP -m BT_BNEP -d BT_LEDS -d BT_DEBUGFS -d BT_HCIBTUSB
fi
scripts/config --file "$out/.config" --set-str LOCALVERSION "-dirty" -d LOCALVERSION_AUTO \
  -e HID_SUPPORT -m HID -m HID_GENERIC -m UHID -m BT_HIDP
make O="$out" olddefconfig
make O="$out" -j8 modules_prepare
cp /work/.build/src/mainline/out/Module.symvers "$out/Module.symvers"
cp --reflink=auto /work/.build/src/mainline/out/vmlinux.o "$out/vmlinux.o"
test "$(cat "$out/include/config/kernel.release")" = "$(cat /work/.build/src/mainline/out/include/config/kernel.release)"
make O="$out" -j8 net/bluetooth/bluetooth.ko net/bluetooth/rfcomm/rfcomm.ko \
  net/bluetooth/bnep/bnep.ko net/bluetooth/hidp/hidp.ko \
  drivers/bluetooth/btbcm.ko drivers/bluetooth/hci_uart.ko \
  crypto/kpp.ko crypto/ecc.ko crypto/ecdh_generic.ko crypto/cmac.ko crypto/aes.ko drivers/hid/hid.ko drivers/hid/hid-generic.ko drivers/hid/uhid.ko
make O="$out" M="$work/driver" -j8 modules
mkdir -p "$work/modules"
find "$out/net/bluetooth" "$out/drivers/bluetooth" "$out/crypto" "$out/drivers/hid" \
  "$work/driver" -name '*.ko' -exec cp '{}' "$work/modules/" \;
