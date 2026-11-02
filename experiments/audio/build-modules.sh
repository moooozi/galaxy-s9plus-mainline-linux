#!/bin/bash
# Run inside s9plus-ubuntu-build, with the port repository mounted at /work.
set -euo pipefail
cd /work/.build/src/mainline
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
out=/work/.build/audio-work/out
driver=/work/.build/audio-work/driver
mkdir -p "$out"
if [ ! -f "$out/.config" ]; then
    cp out/.config "$out/.config"
    scripts/config --file "$out/.config" -m SOUND -m SND -e SND_DRIVERS -m SND_DUMMY \
      -d SND_SOC -d SND_USB -d SND_HRTIMER -d SND_ALOOP -d SND_OSSEMUL \
      -d SND_SEQUENCER -d SND_PCI -d SND_HDA -d SND_SPI -d SND_ARM -d SND_VIRTIO
    make O="$out" olddefconfig
fi
make O="$out" -j8 modules_prepare
# The unchanged kernel's exported symbols are authoritative for dependencies.
cp out/Module.symvers "$out/Module.symvers"
# In-tree modpost reads exports from vmlinux.o, rather than Module.symvers.
cp --reflink=auto out/vmlinux.o "$out/vmlinux.o"
test "$(cat "$out/include/config/kernel.release")" = "$(cat out/include/config/kernel.release)"
make O="$out" -j8 sound/soundcore.ko sound/core/snd.ko sound/core/snd-timer.ko \
  sound/core/snd-pcm.ko drivers/i2c/algos/i2c-algo-bit.ko drivers/i2c/busses/i2c-gpio.ko
make O="$out" M="$driver" -j8 modules
mkdir -p /work/.build/audio-work/modules
cp "$out"/sound/soundcore.ko "$out"/sound/core/snd{,-timer,-pcm}.ko \
  "$out"/drivers/i2c/algos/i2c-algo-bit.ko "$out"/drivers/i2c/busses/i2c-gpio.ko \
  "$driver"/snd-zrn-abox.ko /work/.build/audio-work/modules/
