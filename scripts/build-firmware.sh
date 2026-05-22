#!/usr/bin/env bash
# scripts/build-firmware.sh — fetch Pi Zero 2 W boot firmware
set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BUILD_DIR="$SCRIPT_DIR/.build"
FW_DIR="$BUILD_DIR/firmware"
OUT="$SCRIPT_DIR/dist/boot"
mkdir -p "$FW_DIR" "$OUT"
if [ ! -d "$FW_DIR/.git" ]; then
  echo "==> Cloning Pi firmware"
  git clone --depth=1 --filter=blob:none --sparse \
    https://github.com/raspberrypi/firmware.git "$FW_DIR"
  git -C "$FW_DIR" sparse-checkout set boot
fi
echo "==> Copying boot files"
cp "$FW_DIR"/boot/start.elf "$OUT/"
cp "$FW_DIR"/boot/fixup.dat "$OUT/"
cp "$FW_DIR"/boot/bcm2710-rpi-zero-2-w.dtb "$OUT/"
mkdir -p "$OUT/overlays"
cp "$FW_DIR"/boot/overlays/miniuart-bt.dtbo "$OUT/overlays/"
cat > "$OUT/config.txt" << 'EOF'
dtparam=audio=on
gpu_mem=128
dtoverlay=vc4-kms-v3d
max_framebuffers=2
dtoverlay=miniuart-bt
enable_uart=1
dtoverlay=dwc2,dr_mode=host
arm_64bit=1
kernel=kernel8.img
EOF
echo "console=serial0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 rootwait quiet" \
  > "$OUT/cmdline.txt"
echo "==> Pi firmware ready: $OUT"
