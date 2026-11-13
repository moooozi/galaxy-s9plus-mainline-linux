#!/bin/bash
# Debian 13 headless image. Installs a released embedding package; no compiler.
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=${WORK:-$repo/.build/debian-embedding}
out=${OUT:-$repo/dist/debian-embedding}
root=$work/rootfs
base=https://moooozi.github.io/galaxy-s9plus-kernel
[ "$(id -u)" = 0 ] || { echo 'Run in the build container as root' >&2; exit 1; }
[ ! -e "$root" ] || { echo 'Use a fresh work directory' >&2; exit 1; }
mkdir -p "$work" "$out"
mounts=()
cleanup() { for path in "${mounts[@]}"; do umount -R "$path" || true; done; }
trap cleanup EXIT
debootstrap --arch=arm64 --variant=minbase --include=ca-certificates --foreign \
    --keyring=/usr/share/keyrings/debian-archive-keyring.gpg trixie "$root" https://deb.debian.org/debian
if [ "$(uname -m)" != aarch64 ]; then cp /usr/bin/qemu-aarch64-static "$root/usr/bin/"; fi
[ ! -L "$root/proc" ] || rm "$root/proc"
mkdir -p "$root"/{proc,sys,dev,run}
chroot "$root" /debootstrap/debootstrap --second-stage
mount -t proc proc "$root/proc"; mounts=("$root/proc")
mount -t sysfs sysfs "$root/sys"; mounts=("$root/sys" "${mounts[@]}")
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"; mounts=("$root/dev" "${mounts[@]}")
mount -t tmpfs tmpfs "$root/run"; mounts=("$root/run" "${mounts[@]}")
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"; chmod 755 "$root/usr/sbin/policy-rc.d"
cp /etc/resolv.conf "$root/etc/resolv.conf"
cat > "$root/etc/apt/sources.list" <<'SOURCES'
deb https://deb.debian.org/debian trixie main non-free-firmware
deb https://deb.debian.org/debian trixie-updates main non-free-firmware
deb https://security.debian.org/debian-security trixie-security main non-free-firmware
SOURCES
mkdir -p "$root/etc/apt/keyrings"
cp "$repo/image/releases/keys/archive.asc" "$root/etc/apt/keyrings/s9plus-kernel.asc"
printf 'deb [arch=arm64 signed-by=/etc/apt/keyrings/s9plus-kernel.asc] %s/apt stable main\n' "$base" > "$root/etc/apt/sources.list.d/s9plus-kernel.list"
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive S9PLUS_IMAGE_BUILD=1 \
    apt-get install -y --no-install-recommends systemd-sysv dbus openssh-server sudo \
    network-manager avahi-daemon python3 kmod util-linux iproute2 iputils-ping \
    ca-certificates locales tzdata bash linux-s9plus-embedding
python3 "$repo/scripts/images/configure-rootfs.py" "$root" debian-embedding
chroot "$root" dpkg-query -W > "$out/package-manifest.txt"
chroot "$root" apt-get clean
rm -rf "$root/var/lib/apt/lists/"*
# Preserve a working resolver on the image while NetworkManager starts.
rm -f "$root/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$root/etc/resolv.conf"
cleanup; mounts=()
bash "$repo/scripts/images/finish-image.sh" "$root" "$out" debian-embedding
