#!/usr/bin/env bash
# scripts/build-kernel.sh — fetch pre-built Pi Zero 2 W kernel (arm64)
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BUILD_DIR="$SCRIPT_DIR/.build"
OUT="$SCRIPT_DIR/dist/boot"
FIRMWARE_TAG="${RPI_FIRMWARE_TAG:-stable}"
FIRMWARE_BASE="https://github.com/raspberrypi/firmware/raw/$FIRMWARE_TAG/boot"

mkdir -p "$BUILD_DIR" "$OUT"

echo "==> Fetching pre-built kernel8.img from RPi firmware ($FIRMWARE_TAG)"

# kernel8.img = arm64 kernel for all Pi models including Zero 2 W
if [ ! -f "$BUILD_DIR/kernel8.img" ]; then
  wget -q --show-progress "$FIRMWARE_BASE/kernel8.img" -O "$BUILD_DIR/kernel8.img"
else
  echo "  Cached: kernel8.img"
fi

cp "$BUILD_DIR/kernel8.img" "$OUT/kernel8.img"
echo "==> Kernel ready: $OUT/kernel8.img"
ls -lh "$OUT/kernel8.img"