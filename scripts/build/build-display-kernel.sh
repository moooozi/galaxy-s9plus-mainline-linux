#!/bin/bash
# Run inside the existing s9plus-ubuntu-build container (/work = port repo).
# The isolated source/output copy is prepared on the host; originals stay intact.
set -euo pipefail
repo=/work
work="$repo/.build/display-work"
source="$work/src"
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
test -f "$source/out/.config"
cmp "$repo/.build/src/mainline/out/.config" "$source/out/.config"
install -m644 "$repo/src/gpu/drm/s9p/s9p-decon.c" \
    "$repo/src/gpu/drm/s9p/s9p-panel-self-mask.h" "$source/drivers/gpu/drm/s9p/"
make -C "$source" O=out -j8 Image
test "$(cat "$source/out/include/config/kernel.release")" = 7.1.0-dirty
if [ ! -d "$work/loader" ]; then
    cp -a "$repo/bootloader/uniLoader" "$work/loader"
fi
mkdir -p "$work/loader/blob"
cp "$source/out/arch/arm64/boot/Image" "$work/loader/blob/Image"
cp "$repo/dist/uniloader-in/dtb" "$work/loader/blob/dtb"
printf '' | gzip -n > "$work/loader/blob/ramdisk"
make -C "$work/loader" ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- star2lte_defconfig
make -C "$work/loader" ARCH=aarch64 CROSS_COMPILE=aarch64-linux-gnu- -j8
cmp "$repo/dist/uniloader/boot-s9plus.img.loader.config" "$work/loader/.config"
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, '/work/scripts/build')
from boot_parts import parts
reference = parts(Path('/work/dist/uniloader/boot-s9plus.img').read_bytes())
Path('/work/.build/display-work/dt.img').write_bytes(reference['dt'])
PY
target="$repo/dist/uniloader/boot-s9plus-panel-sram.img"
python3 "$repo/scripts/build/mkboot.py" \
    --ref "$repo/dist/uniloader/boot-s9plus.img" \
    --kernel "$work/loader/uniLoader" --dt "$work/dt.img" -o "$target"
sha256sum "$target" > "$target.sha256"
echo "CANDIDATE_BUILT $target"
