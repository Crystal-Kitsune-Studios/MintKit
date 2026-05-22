#!/usr/bin/env bash
# scripts/build-image.sh
# Assemble the final flashable SD card image
set -euo pipefail
source "$SCRIPT_DIR/config/mintkit.conf"

BOARD=${1:-rk3566}
OUT="$SCRIPT_DIR/dist"
IMG="$OUT/mintkit-${BOARD}.img"
ROOTFS="$SCRIPT_DIR/.build/rootfs"

mkdir -p "$OUT"

echo "==> Creating ${IMAGE_SIZE_MB}MB image file"
dd if=/dev/zero of="$IMG" bs=1M count="$IMAGE_SIZE_MB" status=progress

echo "==> Partitioning"
# GPT layout:
#   Sector 64-8191  : U-Boot
#   Part 1 (FAT32)  : Boot (kernel + DTB)  128MB
#   Part 2 (ext4)   : Rootfs               remaining
parted -s "$IMG" mklabel gpt
parted -s "$IMG" mkpart boot  fat32   4MiB  132MiB
parted -s "$IMG" mkpart root  ext4  132MiB  100%
parted -s "$IMG" set 1 boot on

echo "==> Writing U-Boot at sector 64"
dd if="$OUT/u-boot-rk3566.bin" of="$IMG" seek=64 conv=notrunc bs=512

echo "==> Setting up loop device"
LOOP=$(losetup -fP --show "$IMG")
trap "losetup -d $LOOP" EXIT

echo "==> Formatting partitions"
mkfs.vfat -F 32 -n BOOT  "${LOOP}p1"
mkfs.ext4 -q  -L ROOT  "${LOOP}p2"

echo "==> Copying boot files"
MNT=$(mktemp -d)
mount "${LOOP}p1" "$MNT"
cp "$OUT/boot/Image"      "$MNT/Image"
cp "$OUT/boot/rk3566.dtb" "$MNT/rk3566.dtb"
cat > "$MNT/extlinux/extlinux.conf" << EOF
label MintKit
  kernel /Image
  fdt    /rk3566.dtb
  append root=/dev/mmcblk0p2 rootwait rw console=ttyS2,1500000 \
         quiet splash vt.global_cursor_default=0
EOF
umount "$MNT"

echo "==> Copying rootfs"
mount "${LOOP}p2" "$MNT"
rsync -aHAX --info=progress2 "$ROOTFS/" "$MNT/"
umount "$MNT"
rmdir "$MNT"

echo "==> Image ready: $IMG"
ls -lh "$IMG"
