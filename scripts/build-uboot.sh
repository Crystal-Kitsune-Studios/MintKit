#!/usr/bin/env bash
# scripts/build-uboot.sh
# Cross-compile U-Boot for RK3566 and produce a flashable binary
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
source "$SCRIPT_DIR/config/mintkit.conf"

CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
ARCH="${ARCH:-arm64}"
BUILD_DIR="$SCRIPT_DIR/.build"
OUT="$SCRIPT_DIR/dist"

UBOOT_VER="${UBOOT_VERSION:-2023.10}"
UBOOT_SRC="$BUILD_DIR/u-boot-${UBOOT_VER}"
UBOOT_TAR="$BUILD_DIR/u-boot-${UBOOT_VER}.tar.bz2"

# RK3566 BL31 (ARM Trusted Firmware)
BL31_URL="https://github.com/rockchip-linux/rkbin/raw/master/bin/rk35/rk3568_bl31_v1.44.elf"
BL31="$BUILD_DIR/rk3566-bl31.elf"

mkdir -p "$BUILD_DIR" "$OUT"

# ── 1. Fetch U-Boot source ────────────────────────────────────────────────────
if [ ! -d "$UBOOT_SRC" ]; then
  echo "==> Downloading U-Boot ${UBOOT_VER}"
  if [ ! -f "$UBOOT_TAR" ]; then
    wget -q --show-progress \
      "https://ftp.denx.de/pub/u-boot/u-boot-${UBOOT_VER}.tar.bz2" \
      -O "$UBOOT_TAR"
  fi
  echo "==> Extracting"
  tar -xf "$UBOOT_TAR" -C "$BUILD_DIR"
fi

# ── 2. Fetch BL31 ─────────────────────────────────────────────────────────────
if [ ! -f "$BL31" ]; then
  echo "==> Downloading RK3566 BL31"
  wget -q --show-progress "$BL31_URL" -O "$BL31"
fi

# ── 3. Apply any local patches ────────────────────────────────────────────────
PATCH_DIR="$SCRIPT_DIR/kernel/patches/uboot"
if [ -d "$PATCH_DIR" ]; then
  echo "==> Applying U-Boot patches"
  for p in "$PATCH_DIR"/*.patch; do
    patch -d "$UBOOT_SRC" -p1 < "$p" && echo "  applied: $p"
  done
fi

# ── 4. Build ──────────────────────────────────────────────────────────────────
cd "$UBOOT_SRC"

echo "==> Configuring U-Boot (evb-rk3568 defconfig — closest upstream for RK3566)"
make ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" evb-rk3568_defconfig

echo "==> Compiling U-Boot"
make -j"$(nproc)" \
  ARCH="$ARCH" \
  CROSS_COMPILE="$CROSS_COMPILE" \
  BL31="$BL31" \
  all

# ── 5. Package ────────────────────────────────────────────────────────────────
echo "==> Copying output to dist/"
cp u-boot-rockchip.bin "$OUT/u-boot-rk3566.bin"

echo "==> U-Boot build complete: $OUT/u-boot-rk3566.bin"
ls -lh "$OUT/u-boot-rk3566.bin"
