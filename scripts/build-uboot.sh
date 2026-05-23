#!/usr/bin/env bash
# scripts/build-uboot.sh
# Fetch Raspberry Pi Zero 2 W boot firmware (Pi doesn't use U-Boot)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/config/mintkit.conf"

BUILD_DIR="$SCRIPT_DIR/.build"
OUT="$SCRIPT_DIR/dist/boot"
FIRMWARE_DIR="$BUILD_DIR/rpi-firmware"
FIRMWARE_TAG="${RPI_FIRMWARE_TAG:-stable}"
FIRMWARE_BASE="https://github.com/raspberrypi/firmware/raw/$FIRMWARE_TAG/boot"

mkdir -p "$BUILD_DIR" "$OUT" "$FIRMWARE_DIR/overlays"

echo "==> Fetching Raspberry Pi Zero 2 W boot firmware ($FIRMWARE_TAG)"

FIRMWARE_FILES=(
  "bootcode.bin"
  "start.elf"
  "start_cd.elf"
  "fixup.dat"
  "fixup_cd.dat"
  "bcm2710-rpi-zero-2-w.dtb"
  "bcm2710-rpi-zero-2.dtb"
  "overlays/miniuart-bt.dtbo"
  "overlays/disable-bt.dtbo"
)

for f in "${FIRMWARE_FILES[@]}"; do
  if [ ! -f "$FIRMWARE_DIR/$f" ]; then
    echo "  Downloading: $f"
    wget -q --show-progress "$FIRMWARE_BASE/$f" -O "$FIRMWARE_DIR/$f"
  else
    echo "  Cached: $f"
  fi
done

cp -r "$FIRMWARE_DIR/"* "$OUT/"

cat > "$OUT/config.txt" <<'EOF'
arm_64bit=1
kernel=kernel8.img
gpu_mem=64
dtoverlay=miniuart-bt
enable_uart=1
disable_overscan=1
framebuffer_width=256
framebuffer_height=240
EOF

cat > "$OUT/cmdline.txt" <<'EOF'
console=serial0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait quiet
EOF

echo "==> Pi Zero 2 W firmware ready: $OUT"
ls -lh "$OUT/"
