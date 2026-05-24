#!/usr/bin/env bash
# scripts/build-rootfs.sh — build minimal Debian rootfs for PocketMint
set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BUILD_DIR="$SCRIPT_DIR/.build"
ROOTFS="$BUILD_DIR/rootfs"
LAUNCHER_SRC="$SCRIPT_DIR/rootfs/launcher/mintos.py"
GAME_SRC="$SCRIPT_DIR/rootfs/games"
mkdir -p "$ROOTFS"
echo "==> Bootstrapping Debian (bookworm) for arm64"
debootstrap --arch=arm64 --foreign \
  --components=main,contrib,non-free,non-free-firmware \
  bookworm "$ROOTFS" http://deb.debian.org/debian
cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/"
chroot "$ROOTFS" /debootstrap/debootstrap --second-stage
echo "==> Installing packages"
chroot "$ROOTFS" apt-get update -qq
chroot "$ROOTFS" apt-get install -y --no-install-recommends \
  python3 python3-pygame python3-pip \
  fbset psmisc openssh-server \
  firmware-brcm80211 wpasupplicant \
  alsa-utils \
  udev systemd-sysv
echo "==> Configuring hostname & users"
echo "pocketmint" > "$ROOTFS/etc/hostname"
chroot "$ROOTFS" useradd -m -s /bin/bash mintkit
echo "mintkit:mintkit" | chroot "$ROOTFS" chpasswd
mkdir -p "$ROOTFS/etc/sudoers.d"
echo "mintkit ALL=(ALL) NOPASSWD: ALL" > "$ROOTFS/etc/sudoers.d/mintkit"
echo "==> Serial console (serial0 / ttyAMA0)"
chroot "$ROOTFS" systemctl enable serial-getty@ttyAMA0.service
echo "==> Copying launcher"
install -Dm755 "$LAUNCHER_SRC" "$ROOTFS/home/mintkit/mintos.py"
echo "==> Copying games"
cp -r "$GAME_SRC"/* "$ROOTFS/home/mintkit/" 2>/dev/null || true
echo "==> Installing systemd service"
install -Dm644 "$SCRIPT_DIR/rootfs/etc/systemd/system/mintkit.service" \
  "$ROOTFS/etc/systemd/system/mintkit.service"
chroot "$ROOTFS" systemctl enable mintkit.service
echo "==> Installing udev rules"
install -Dm644 "$SCRIPT_DIR/rootfs/etc/udev/rules.d/99-mintkit.rules" \
  "$ROOTFS/etc/udev/rules.d/99-mintkit.rules"
echo "==> Rootfs build complete: $ROOTFS"
