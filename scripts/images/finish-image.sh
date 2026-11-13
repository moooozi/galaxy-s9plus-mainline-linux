#!/bin/bash
set -euo pipefail
root=$1
out=$2
variant=$3
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$out"
kernel=full
[ "$variant" != debian-embedding ] || kernel=embedding
cp "$root/usr/share/s9plus-kernel/$kernel/boot-s9plus.img" "$out/boot-s9plus.img"
cp "$root/usr/share/s9plus-kernel/$kernel/kernel-manifest.json" "$out/kernel-manifest.json"
# Confirm installed modules and staged BOOT belong to this variant.
python3 "$repo/scripts/images/validate-rootfs.py" "$root" "$variant"
rm -f "$root/usr/sbin/policy-rc.d" "$root/usr/bin/qemu-aarch64-static"
: > "$root/etc/machine-id"
rm -f "$root"/etc/ssh/ssh_host_*
# mke2fs -d doesn't mount the target image or require a loop device.
. "$repo/image/common/lib.sh"
make_ext4 "$root" "$out/s9plus-rootfs.img" s9plus-root
zstd -T0 -6 --rm "$out/s9plus-rootfs.img"
cp "$repo/docs/new-images.md" "$out/INSTALL.md"
(cd "$out" && sha256sum ./* > SHA256SUMS)
