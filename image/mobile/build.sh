#!/bin/bash
# Fresh single-shell Ubuntu 26.10 image; run as root on native ARM64.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PROFILE=$REPO/image/mobile
. "$REPO/image/common/lib.sh"
VARIANT=${1:?usage: build.sh kde or gnome}
case "$VARIANT" in
    kde) SESSION=plasma-mobile; IMAGE_DISPLAY_MANAGER=sddm.service; IMAGE_DISPLAY_MANAGER_EXEC=/usr/bin/sddm ;;
    gnome) SESSION=gnome; IMAGE_DISPLAY_MANAGER=gdm.service; IMAGE_DISPLAY_MANAGER_EXEC=/usr/sbin/gdm3 ;;
    *) die 'variant must be kde or gnome' ;;
esac
[ "$(uname -m)" = aarch64 ] || die 'Use a native ARM64 build host/container'
require_host kmod tar zstd
UBUNTU_SUITE=stonking
WORK=${WORK:-/build/s9plus-$VARIANT}
OUT=${OUT:-$REPO/dist/$VARIANT-mobile}
KERNEL_DIR=${KERNEL_DIR:-$REPO/.build/inputs/kernel}
GNOME_DIR=${GNOME_DIR:-$REPO/.build/inputs/gnome}
[ ! -e "$WORK/rootfs" ] || die 'Use a fresh work directory'
mkdir -p "$WORK" "$OUT"
[ -z "$(ls -A "$OUT")" ] || die 'Output directory must be empty'
IMAGE_PASSWORD=${IMAGE_PASSWORD:-changeme}
image_settings s9plus
R=$WORK/rootfs
# Recursive /dev bindings are also correct in rootless privileged containers.
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
# The generic Ubuntu debootstrap script is shared between suite aliases.
bootstrap_script=/usr/share/debootstrap/scripts/stonking
[ -e "$bootstrap_script" ] || bootstrap_script=/usr/share/debootstrap/scripts/resolute
bootstrap_failed() {
    tail -n 100 "$R/debootstrap/debootstrap.log" >&2 || true
    die 'Ubuntu bootstrap failed (debootstrap diagnostics above)'
}
# Split stages even on native ARM64. In Docker, debootstrap leaves /proc ->
# /proc after extraction. Rust coreutils then aborts on that circular link
# before the second stage can mount procfs. An empty directory is safe.
debootstrap --arch=arm64 --variant=minbase --include=ca-certificates --foreign \
    --keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg \
    stonking "$R" "$UBUNTU_MIRROR" "$bootstrap_script" || bootstrap_failed
if [ -L "$R/proc" ]; then
    [ "$(readlink "$R/proc")" = /proc ] || die 'Unexpected bootstrap /proc symlink'
    rm "$R/proc"
fi
mkdir -p "$R/proc"
chroot "$R" /debootstrap/debootstrap --second-stage || bootstrap_failed
chroot_mount "$R"
copy_tree "$COMMON_DIR/rootfs" "$R"
rm -f "$R/etc/apt/sources.list" "$R/etc/resolv.conf"
cp /etc/resolv.conf "$R/etc/resolv.conf"
cat > "$R/etc/apt/sources.list.d/ubuntu.sources" <<EOF
Types: deb
URIs: $UBUNTU_MIRROR
Suites: stonking stonking-updates stonking-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"
chmod 755 "$R/usr/sbin/policy-rc.d"
pkgs=$(sed 's/#.*//' "$PROFILE/common-packages.txt" "$PROFILE/$VARIANT-packages.txt" | tr '\n' ' ')
in_chroot "$R" apt-get -o APT::Update::Error-Mode=any update
# Shared GDM/SDDM conffiles and device files are supplied explicitly below.
in_chroot "$R" apt-get -y --no-install-recommends -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold install $pkgs
if [ "$VARIANT" = gnome ]; then
    python3 "$REPO/scripts/ci/install-mobile-debs.py" "$R" "$GNOME_DIR"
fi
rootfs_configure "$R"
rootfs_device "$R" "$REPO/device/base" "$REPO/device/configure.sh"
copy_tree "$PROFILE/rootfs" "$R"
in_chroot "$R" systemctl enable s9plus-boot-errors.service
python3 "$REPO/scripts/ci/install-mobile-firefox.py" "$WORK/s9plus-mobile-firefox.deb"
cp "$WORK/s9plus-mobile-firefox.deb" "$R/tmp/s9plus-mobile-firefox.deb"
in_chroot "$R" dpkg -i /tmp/s9plus-mobile-firefox.deb
rm "$R/tmp/s9plus-mobile-firefox.deb"
# Leave global scaling automatic: forcing 3 makes Mutter advertise unsupported
# preferred scales for lower modes. The display initializer owns first-run size.
# Type the empty dconf string array; retain only the selected shell's policy.
cat > "$R/etc/dconf/db/local.d/00-phone" <<'EOF'
[org/gnome/desktop/a11y/applications]
screen-keyboard-enabled=true

[org/gnome/desktop/interface]
scaling-factor=uint32 0
gtk-theme='Adwaita'
icon-theme='Adwaita'

[org/gnome/shell]
enabled-extensions=@as []
EOF
printf 'CHASSIS=handset\n' > "$R/etc/machine-info"
install -d -m 755 "$R/var/lib/AccountsService/users" "$R/home/$IMAGE_USER/.config/autostart"
cat > "$R/var/lib/AccountsService/users/$IMAGE_USER" <<EOF
[User]
Session=$SESSION
XSession=$SESSION
SystemAccount=false
EOF
chmod 600 "$R/var/lib/AccountsService/users/$IMAGE_USER"
if [ "$VARIANT" = kde ]; then
    install -d "$R/etc/sddm.conf.d" "$R/etc/systemd/system/sddm.service.d"
    cat > "$R/etc/sddm.conf.d/10-mobile.conf" <<EOF
[General]
DisplayServer=wayland
[Wayland]
CompositorCommand=/usr/bin/kwin_wayland --no-lockscreen --no-global-shortcuts --locale1
[Theme]
Current=breeze
[Autologin]
User=$IMAGE_USER
Session=plasma-mobile.desktop
Relogin=false
EOF
    cp "$REPO/device/base/etc/systemd/system/gdm.service.d/10-wait-for-render-node.conf" \
        "$R/etc/systemd/system/sddm.service.d/10-wait-for-render-node.conf"
    in_chroot "$R" systemctl disable plasma-mobile.service
    install -m 755 "$REPO/image/ubuntu-26.10/s9plus-plasma-display" "$R/usr/local/bin/s9plus-plasma-display"
    python3 "$REPO/image/ubuntu-26.10/fix-mobile-settings-links.py" "$R"
    cat > "$R/home/$IMAGE_USER/.config/kwinrc" <<'EOF'
[Wayland]
InputMethod=/usr/share/applications/org.kde.plasma.keyboard.desktop
VirtualKeyboardEnabled=true
EOF
    EXEC=/usr/local/bin/s9plus-plasma-display
    DESKTOP=KDE
    ln -sfn /usr/lib/systemd/system/sddm.service "$R/etc/systemd/system/display-manager.service"
else
    printf 'FallbackSession=gnome\n' >> "$R/etc/gdm3/custom.conf"
    install -d "$R/etc/systemd/user/org.gnome.Shell@.service.d"
    cat > "$R/etc/systemd/user/org.gnome.Shell@.service.d/20-s9plus-touch-wakeup.conf" <<'EOF'
[Service]
Environment=MUTTER_TOUCHSCREEN_WAKEUP=double-tap
EOF
    ln -sfn /usr/lib/systemd/system/gdm.service "$R/etc/systemd/system/display-manager.service"
    install -m 755 "$PROFILE/gnome-display.py" "$R/usr/local/bin/s9plus-gnome-display"
    EXEC=/usr/local/bin/s9plus-gnome-display
    DESKTOP=GNOME
fi
cat > "$R/home/$IMAGE_USER/.config/autostart/s9plus-display.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Phone display scale
Exec=$EXEC
OnlyShowIn=$DESKTOP;
NoDisplay=true
EOF
in_chroot "$R" chown -R "$IMAGE_USER:$IMAGE_USER" "/home/$IMAGE_USER/.config"
in_chroot "$R" dconf update
python3 "$REPO/scripts/ci/install-kernel-modules.py" "$R" "$KERNEL_DIR"
copy_tree "$REPO/experiments/audio/rootfs" "$R"
copy_tree "$REPO/experiments/bluetooth/rootfs" "$R"
# Firmware and identity belong to the owner and are not included in public images.
install -d "$R/etc/systemd/system/s9plus-bluetooth.service.d"
cat > "$R/etc/systemd/system/s9plus-bluetooth.service.d/10-own-address.conf" <<'EOF'
[Unit]
ConditionPathExists=/var/lib/s9plus-bluetooth/bt_addr
EOF
ln -sfn bcm4361B2_semco.hcd "$R/usr/lib/firmware/brcm/BCM.samsung,star2lte.hcd"
in_chroot "$R" systemctl enable s9plus-audio.service s9plus-bluetooth.service
printf 'fuse\n' > "$R/etc/modules-load.d/s9plus-fuse.conf"
in_chroot "$R" dpkg-query -W > "$OUT/package-manifest.txt"
cp "$KERNEL_DIR/kernel-manifest.json" "$OUT/kernel-manifest.json"
cp "$KERNEL_DIR/boot-s9plus.img" "$OUT/boot-s9plus.img"
if [ "$VARIANT" = gnome ]; then cp "$GNOME_DIR/sources.json" "$OUT/gnome-sources.json"; fi
rootfs_finish "$R"
python3 "$REPO/scripts/ci/validate-mobile-rootfs.py" "$R" "$VARIANT" "$OUT/kernel-manifest.json"
chroot_umount
make_ext4 "$R" "$OUT/s9plus-rootfs.img" s9plus-root
zstd -T0 -8 --rm "$OUT/s9plus-rootfs.img"
cp "$REPO/docs/03-installing.md" "$OUT/INSTALL.md"
checksums "$OUT"
log "$VARIANT Mobile image ready in $OUT"
