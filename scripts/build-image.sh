#!/usr/bin/env bash
# scripts/build-image.sh — assemble Pi Zero 2 W flashable .img
set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
source "$SCRIPT_DIR/config/mintkit.conf"
OUT="$SCRIPT_DIR/dist"
IMG="$OUT/mintkit-pizero2w.img"
ROOTFS="$SCRIPT_DIR/.build/rootfs"
BOOT_SRC="$SCRIPT_DIR/dist/boot"
mkdir -p "$OUT"
echo "==> Creating ${IMAGE_SIZE_MB}MB image"
dd if=/dev/zero of="$IMG" bs=1M count="$IMAGE_SIZE_MB" status=progress
echo "==> Partitioning (FAT32 boot + ext4 rootfs)"
parted -s "$IMG" mklabel msdos
parted -s "$IMG" mkpart primary fat32  1MiB  65MiB
parted -s "$IMG" mkpart primary ext4  65MiB 100%
parted -s "$IMG" set 1 boot on
LOOP=$(losetup -fP --show "$IMG")
trap "losetup -d $LOOP" EXIT
mkfs.vfat -F 32 -n BOOT "${LOOP}p1"
mkfs.ext4 -q   -L ROOT "${LOOP}p2"
MNT=$(mktemp -d)
echo "==> Writing boot partition"
mount "${LOOP}p1" "$MNT"
cp -r "$BOOT_SRC/"* "$MNT/"
umount "$MNT"
echo "==> Writing rootfs partition"
mount "${LOOP}p2" "$MNT"
rsync -aHAX --info=progress2 "$ROOTFS/" "$MNT/"
umount "$MNT"
rmdir "$MNT"
echo "==> Image ready: $IMG"
ls -lh "$IMG"
