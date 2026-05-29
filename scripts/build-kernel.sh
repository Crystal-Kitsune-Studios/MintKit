#!/usr/bin/env bash
# scripts/build-kernel.sh — copy pre-installed kernel from rootfs
# Requires build-rootfs.sh to have run first (installs raspberrypi-kernel via apt)
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.."; pwd)}"
BUILD_DIR="$SCRIPT_DIR/.build"
ROOTFS="$BUILD_DIR/rootfs"
OUT="$SCRIPT_DIR/dist/boot"

mkdir -p "$OUT"

if [ ! -f "$ROOTFS/boot/kernel8.img" ]; then
  echo "ERROR: $ROOTFS/boot/kernel8.img not found."
  echo "       Run build-rootfs.sh first (installs raspberrypi-kernel via apt)."
  exit 1
fi

echo "==> Copying kernel8.img from rootfs apt install"
cp "$ROOTFS/boot/kernel8.img" "$OUT/kernel8.img"
echo "==> kernel8.img ready"
ls -lh "$OUT/kernel8.img"