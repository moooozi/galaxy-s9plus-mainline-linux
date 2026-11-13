#!/bin/bash
# Native aarch64 container: assemble a rootfs from signed binary packages.
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
variant=${1:?postmarketos-plasma or postmarketos-phosh}
case "$variant" in
postmarketos-plasma) ui=plasma-mobile ;;
postmarketos-phosh) ui=phosh ;;
*) exit 1 ;;
esac
work=${WORK:-$repo/.build/$variant}
out=${OUT:-$repo/dist/$variant}
root=$work/rootfs
[ "$(id -u)" = 0 ] || { echo 'Run as container root' >&2; exit 1; }
[ "$(uname -m)" = aarch64 ] || { echo 'Use a native ARM64 build runner' >&2; exit 1; }
[ ! -e "$root" ] || { echo 'Use a fresh build directory' >&2; exit 1; }
mkdir -p "$root/etc/apk/keys" "$root/etc" "$root/dev" "$root/proc" "$root/sys" "$out"
cp /etc/apk/keys/* "$root/etc/apk/keys/"
cp "$repo/image/releases/keys/build.postmarketos.org.rsa.pub" "$repo/image/releases/keys/s9plus.rsa.pub" "$root/etc/apk/keys/"
cat > "$root/etc/apk/repositories" <<'REPOS'
https://mirror.postmarketos.org/postmarketos/extra-repos/systemd/v26.06
https://mirror.postmarketos.org/postmarketos/v26.06
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community
https://moooozi.github.io/galaxy-s9plus-kernel/apk
REPOS
cp /etc/resolv.conf "$root/etc/resolv.conf"
mounts=()
cleanup() { for path in "${mounts[@]}"; do umount -R "$path" || true; done; }
trap cleanup EXIT
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"; mounts=("$root/dev")
mount -t proc proc "$root/proc"; mounts=("$root/proc" "${mounts[@]}")
mount -t sysfs sysfs "$root/sys"; mounts=("$root/sys" "${mounts[@]}")
# apk trusts only the pinned distribution/repository keys above. Scripts run
# in the new root; the kernel hook explicitly stages BOOT during image builds.
S9PLUS_IMAGE_BUILD=1 apk --root "$root" --arch aarch64 add --initdb \
    postmarketos-base postmarketos-base-systemd "postmarketos-ui-$ui" \
    linux-s9plus python3 bash shadow sudo networkmanager networkmanager-wifi \
    avahi openssh-server-pam kmod util-linux alsa-utils bluez mesa-dri-gallium py3-pillow
python3 "$repo/scripts/images/configure-rootfs.py" "$root" "$variant"
chroot "$root" apk info -v > "$out/package-manifest.txt"
cleanup; mounts=()
bash "$repo/scripts/images/finish-image.sh" "$root" "$out" "$variant"
