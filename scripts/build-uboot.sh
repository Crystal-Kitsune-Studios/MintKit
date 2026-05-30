#!/usr/bin/env bash
# scripts/build-uboot.sh
# Fetch Raspberry Pi Zero 2 W boot firmware (Pi doesn't use U-Boot)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/rootfs/config/mintkit.conf"

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
  "overlays/vc4-fkms-v3d.dtbo"
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

# Generate config.txt — Waveshare 4" HDMI IPS 800x480 display
# NOTE: framebuffer_width=256/height=240 causes display hang on this display.
# Must force HDMI hotplug + set CVT mode for 800x480 @ 60Hz.
cat > "$OUT/config.txt" <<'EOF'
arm_64bit=1
kernel=kernel8.img
gpu_mem=64
dtoverlay=miniuart-bt
enable_uart=1

# Waveshare 4" HDMI IPS 800x480 — required or display hangs on color splash
hdmi_force_hotplug=1
hdmi_drive=2
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
framebuffer_width=800
framebuffer_height=480
disable_overscan=1

# KMS for SDL2/pygame kmsdrm display driver
dtoverlay=vc4-fkms-v3d
EOF

# Generate cmdline.txt — removed 'quiet' so boot errors are visible
cat > "$OUT/cmdline.txt" <<'EOF'
console=serial0,115200 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait
EOF

echo "==> Pi Zero 2 W firmware ready: $OUT"
ls -lh "$OUT/"