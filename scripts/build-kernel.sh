#!/usr/bin/env bash
# scripts/build-kernel.sh — cross-compile Pi kernel for Zero 2 W
set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
ARCH="${ARCH:-arm64}"
BUILD_DIR="$SCRIPT_DIR/.build"
OUT="$SCRIPT_DIR/dist/boot"
KERNEL_SRC="$BUILD_DIR/linux-rpi"
mkdir -p "$BUILD_DIR" "$OUT"
if [ ! -d "$KERNEL_SRC/.git" ]; then
  echo "==> Cloning Raspberry Pi kernel (rpi-6.1.y) — this is large"
  git clone --depth=1 --branch rpi-6.1.y \
    https://github.com/raspberrypi/linux.git "$KERNEL_SRC"
fi
cd "$KERNEL_SRC"
echo "==> Configuring for Pi Zero 2 W (bcm2711_defconfig)"
make ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" bcm2711_defconfig
if [ -f "$SCRIPT_DIR/config/kernel.config" ]; then
  echo "==> Merging MintKit overrides"
  scripts/kconfig/merge_config.sh .config "$SCRIPT_DIR/config/kernel.config"
fi
echo "==> Building kernel ($(nproc) threads)"
make -j"$(nproc)" ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" Image modules dtbs
echo "==> Copying output"
cp arch/arm64/boot/Image "$OUT/kernel8.img"
cp arch/arm64/boot/dts/broadcom/bcm2710-rpi-zero-2-w.dtb "$OUT/"
make ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" \
  INSTALL_MOD_PATH="$BUILD_DIR/rootfs" modules_install
echo "==> Kernel build complete"
ls -lh "$OUT/"
