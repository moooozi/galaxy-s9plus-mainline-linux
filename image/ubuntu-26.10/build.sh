#!/bin/bash
# Run inside s9plus-resolute-build. Resume using successful stage markers.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PROFILE=$REPO/image/ubuntu-26.10
. "$REPO/image/common/lib.sh"
UBUNTU_SUITE=stonking
WORK=$REPO/.build/stonking-image-work
R=$WORK/rootfs
OUT=$REPO/dist/stonking-mobile
mkdir -p "$WORK" "$OUT"
exec 9>"$WORK/build.lock"
flock -n 9 || die 'another build is running'
IMAGE_USER=ubuntu
IMAGE_HOSTNAME=s9plus
IMAGE_TIMEZONE=Europe/Berlin
IMAGE_LOCALE=en_US.UTF-8
IMAGE_KEYMAP=us
IMAGE_SSH_KEY=
# Honor the user's chosen simple password, bypassing the old helper's length rule.
IMAGE_PASSWORD_HASH=$(openssl passwd -6 -stdin < "$REPO/.build/initial-password")

chroot_mount() {
    local R=$1
    mkdir -p "$R"/{proc,sys,dev,run}
    _mounts=("$R/run" "$R/dev" "$R/sys" "$R/proc")
    mount -t proc proc "$R/proc"
    mount -t sysfs sysfs "$R/sys"
    mount --rbind /dev "$R/dev"
    mount --make-rslave "$R/dev"
    mount -t tmpfs tmpfs "$R/run"
}
trap chroot_umount EXIT
if ! mountpoint -q /proc/sys/fs/binfmt_misc; then
    mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
fi
if [ ! -f /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
    cat /usr/lib/binfmt.d/qemu-aarch64.conf > /proc/sys/fs/binfmt_misc/register
fi
grep -q 'flags:.*F' /proc/sys/fs/binfmt_misc/qemu-aarch64 || die 'ARM64 binfmt needs F flag'

if [ ! -f "$WORK/bootstrap.done" ]; then
    if [ ! -f "$WORK/foreign.done" ]; then
        log 'Bootstrap Ubuntu 26.10 ARM64'
        # Resolute container predates the suite alias; its generic Ubuntu script
        # supports future suites. The signed Stonking archive supplies all packages.
        debootstrap --arch=arm64 --variant=minbase --include=ca-certificates \
            --keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg --foreign \
            stonking "$R" "$UBUNTU_MIRROR" /usr/share/debootstrap/scripts/resolute
        touch "$WORK/foreign.done"
    fi
    chroot "$R" /debootstrap/debootstrap --second-stage
    touch "$WORK/bootstrap.done"
fi
chroot_mount "$R"
if [ ! -f "$WORK/packages.done" ]; then
    log 'Install vanilla GNOME and phone base packages'
    rm -f "$R/etc/apt/sources.list"
    cat > "$R/etc/apt/sources.list.d/ubuntu.sources" <<EOF
Types: deb
URIs: $UBUNTU_MIRROR
Suites: stonking stonking-updates stonking-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
    copy_tree "$COMMON_DIR/rootfs" "$R"
    rm -f "$R/etc/resolv.conf"
    cp /etc/resolv.conf "$R/etc/resolv.conf"
    printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"
    chmod 755 "$R/usr/sbin/policy-rc.d"
    pkgs=$(sed 's/#.*//' "$PROFILE/packages.txt" | tr '\n' ' ')
    in_chroot "$R" apt-get -o APT::Update::Error-Mode=any update
    in_chroot "$R" apt-get -y --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install $pkgs
    in_chroot "$R" apt-get -y --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade
    touch "$WORK/packages.done"
fi
if [ ! -f "$WORK/plasma-packages.done" ]; then
    log 'Install precompiled Plasma Mobile and Kubuntu defaults'
    CACHE=$REPO/.build/stonking-apt-cache
    mkdir -p "$CACHE"
    if compgen -G "$CACHE/*.deb" >/dev/null; then
        cp -anl "$CACHE"/*.deb "$R/var/cache/apt/archives/"
    fi
    pkgs=$(sed 's/#.*//' "$PROFILE/plasma-packages.txt" | tr '\n' ' ')
    in_chroot "$R" apt-get -y --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold install $pkgs
    # Retain every download outside the image, even after the finish stage cleans APT.
    cp -anl "$R"/var/cache/apt/archives/*.deb "$CACHE"/
    touch "$WORK/plasma-packages.done"
fi
if [ ! -f "$WORK/configure-mobile.done" ]; then
    # The shared configure helper creates the user. Make that step resumable.
    if ! in_chroot "$R" id "$IMAGE_USER" >/dev/null 2>&1; then
        in_chroot "$R" useradd -m -s /bin/bash -G sudo,adm,video,render,audio,input,plugdev,netdev,dialout "$IMAGE_USER"
    fi
    # Use a scoped copy of the shared helper, omitting its now-completed useradd.
    eval "$(declare -f rootfs_configure | sed '/in_chroot .* useradd /d')"
    rootfs_configure "$R"
    rootfs_device "$R" "$REPO/device/base" "$REPO/device/configure.sh"
    test -x "$R/usr/sbin/gdm3"
    test -f "$R/usr/share/wayland-sessions/gnome.desktop"
    install -d "$R/var/lib/AccountsService/users"
    cat > "$R/var/lib/AccountsService/users/ubuntu" <<EOF
[User]
Session=plasma-mobile
XSession=plasma-mobile
SystemAccount=false
EOF
    chmod 600 "$R/var/lib/AccountsService/users/ubuntu"
    cat >> "$R/etc/gdm3/custom.conf" <<EOF
FallbackSession=plasma-mobile
EOF
    cat > "$R/etc/dconf/db/local.d/00-phone" <<'EOF'
[org/gnome/desktop/a11y/applications]
screen-keyboard-enabled=true

[org/gnome/desktop/interface]
scaling-factor=uint32 3
gtk-theme='Adwaita'
icon-theme='Adwaita'

[org/gnome/shell]
enabled-extensions=@as []
EOF
    in_chroot "$R" dconf update
    test -f "$R/usr/share/wayland-sessions/plasma-mobile.desktop"
    test -x "$R/usr/bin/startplasmamobile"
    # The packaged direct-login service would compete with GDM for the seat.
    in_chroot "$R" systemctl disable plasma-mobile.service
    install -d "$R/home/ubuntu/.config/autostart"
    install -m 755 "$PROFILE/s9plus-plasma-display" "$R/usr/local/bin/s9plus-plasma-display"
    cat > "$R/home/ubuntu/.config/autostart/s9plus-plasma-display.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Phone display scale
Exec=/usr/local/bin/s9plus-plasma-display
OnlyShowIn=KDE;
NoDisplay=true
EOF
    test -f "$R/usr/share/applications/org.kde.plasma.keyboard.desktop"
    test -x "$R/usr/bin/kscreen-doctor"
    cat > "$R/home/ubuntu/.config/kwinrc" <<EOF
[Wayland]
InputMethod=/usr/share/applications/org.kde.plasma.keyboard.desktop
VirtualKeyboardEnabled=true
EOF
    in_chroot "$R" chown -R ubuntu:ubuntu /home/ubuntu/.config
    touch "$WORK/configure-mobile.done"
fi
if [ ! -f "$WORK/fuse-module.done" ]; then
    log 'Install matching FUSE module for the document portal'
    KREL=7.1.0-dirty
    KOUT=$REPO/.build/src/mainline/out
    test "$(cat "$KOUT/include/config/kernel.release")" = "$KREL"
    install -D -m 644 "$KOUT/fs/fuse/fuse.ko" "$R/usr/lib/modules/$KREL/kernel/fs/fuse/fuse.ko"
    install -m 644 "$KOUT/modules.builtin" "$KOUT/modules.builtin.modinfo" "$R/usr/lib/modules/$KREL/"
    printf 'kernel/fs/fuse/fuse.ko\n' > "$R/usr/lib/modules/$KREL/modules.order"
    printf 'fuse\n' > "$R/etc/modules-load.d/s9plus-fuse.conf"
    in_chroot "$R" depmod -a "$KREL"
    touch "$WORK/fuse-module.done"
fi
# Restore normal utility selection after the build-only acceleration.
python3 - "$R" "$WORK/build-gnu-aliases.json" <<'PY_CLEAN'
import json, os, sys
from pathlib import Path
r=Path(sys.argv[1]); manifest=Path(sys.argv[2])
if manifest.exists():
    for relative, target in json.loads(manifest.read_text()):
        path=r/relative.lstrip('/')
        if not os.path.lexists(path): continue
        if not path.is_symlink() or os.readlink(path) != target:
            raise SystemExit('Unexpected build alias: '+str(path))
        path.unlink()
    manifest.rename(manifest.with_suffix('.removed.json'))
PY_CLEAN
if [ ! -f "$WORK/finish-mobile.done" ]; then
    rootfs_finish "$R"
    touch "$WORK/finish-mobile.done"
fi
# Normalize the Debian-created gdm3 alias to the actual canonical unit.
ln -sfn /usr/lib/systemd/system/gdm.service "$R/etc/systemd/system/display-manager.service"
log 'Validate final rootfs'
test ! -f "$WORK/build-gnu-aliases.json"
grep -qx 'FallbackSession=plasma-mobile' "$R/etc/gdm3/custom.conf"
grep -qx 'Session=plasma-mobile' "$R/var/lib/AccountsService/users/ubuntu"
test -f "$R/usr/share/wayland-sessions/gnome.desktop"
test -f "$R/usr/share/wayland-sessions/plasma-mobile.desktop"
test -z "$(in_chroot "$R" dpkg --audit)"
grep -q 'VERSION_ID="26.10"' "$R/etc/os-release"
in_chroot "$R" dpkg-query -W gnome-shell 'libmutter-*-0' gnome-session gdm3 libgl1-mesa-dri plasma-mobile plasma-workspace kwin-wayland plasma-keyboard > "$OUT/package-versions.txt"
in_chroot "$R" dpkg-query -W > "$OUT/package-manifest.txt"
in_chroot "$R" passwd -S root | grep -q ' L '
in_chroot "$R" id ubuntu
for g in sudo video render input; do in_chroot "$R" id -nG ubuntu | tr ' ' '\n' | grep -qx "$g"; done
test -L "$R/lib"
test -e "$R/lib/ld-linux-aarch64.so.1"
test -s "$R/lib/firmware/brcm/brcmfmac4361-pcie.bin"
grep -qx 'PAN_MAX_AFBC_PACKING_RATIO=0' "$R/etc/environment"
! compgen -G "$R/etc/ssh/ssh_host_*" >/dev/null
test ! -e "$R/usr/bin/qemu-aarch64-static"
for service in usb-gadget s9p-touch-power s9p-stability s9p-wifi-guard NetworkManager grow-rootfs first-boot-ssh-keys gdm; do
    in_chroot "$R" systemctl is-enabled "$service.service"
done
for target in sleep suspend hibernate hybrid-sleep suspend-then-hibernate; do
    test "$(readlink "$R/etc/systemd/system/$target.target")" = /dev/null
done
if in_chroot "$R" dpkg-query -W -f='${db:Status-Status}\n' ubuntu-session gnome-shell-extension-ubuntu-dock 2>/dev/null | grep -qx installed; then
    die 'Unexpected Ubuntu desktop customization installed'
fi
chroot_umount
if [ ! -f "$WORK/image-mobile.done" ]; then
    make_ext4 "$R" "$OUT/s9plus-rootfs.img" s9plus-root
    checksums "$OUT"
    touch "$WORK/image-mobile.done"
fi
log 'Ubuntu 26.10 / Kubuntu packages: Plasma Mobile default, GNOME alternative, image ready'
