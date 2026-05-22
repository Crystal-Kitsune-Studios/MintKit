#!/usr/bin/env bash
# scripts/build-kernel.sh
# Cross-compile Linux kernel for RK3566 and produce Image + DTB
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
source "$SCRIPT_DIR/config/mintkit.conf"

CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
ARCH="${ARCH:-arm64}"
BOARD="${1:-rk3566}"
BUILD_DIR="$SCRIPT_DIR/.build"
OUT="$SCRIPT_DIR/dist/boot"

KERNEL_VER="${KERNEL_VERSION:-6.1}"
# Use Rockchip BSP kernel for full RK3566 support
KERNEL_REPO="https://github.com/rockchip-linux/kernel.git"
KERNEL_BRANCH="develop-5.10"
KERNEL_SRC="$BUILD_DIR/linux-${KERNEL_VER}"

mkdir -p "$BUILD_DIR" "$OUT"

# ── 1. Fetch kernel source ────────────────────────────────────────────────────
if [ ! -d "$KERNEL_SRC/.git" ]; then
  echo "==> Cloning Rockchip BSP kernel (branch: $KERNEL_BRANCH)"
  echo "    This is large — grab a coffee."
  git clone --depth=1 \
    --branch "$KERNEL_BRANCH" \
    "$KERNEL_REPO" \
    "$KERNEL_SRC"
fi

# ── 2. Apply local patches ────────────────────────────────────────────────────
PATCH_DIR="$SCRIPT_DIR/kernel/patches/kernel"
if [ -d "$PATCH_DIR" ]; then
  echo "==> Applying kernel patches"
  for p in "$PATCH_DIR"/*.patch; do
    patch -d "$KERNEL_SRC" -p1 < "$p" && echo "  applied: $p"
  done
fi

# ── 3. Configure ─────────────────────────────────────────────────────────────
cd "$KERNEL_SRC"

echo "==> Copying MintKit kernel config"
cp "$SCRIPT_DIR/config/kernel.config" .config

echo "==> Running olddefconfig"
make ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" olddefconfig

# ── 4. Compile ────────────────────────────────────────────────────────────────
echo "==> Building kernel Image ($(nproc) threads)"
make -j"$(nproc)" \
  ARCH="$ARCH" \
  CROSS_COMPILE="$CROSS_COMPILE" \
  Image

echo "==> Building device tree blobs"
make -j"$(nproc)" \
  ARCH="$ARCH" \
  CROSS_COMPILE="$CROSS_COMPILE" \
  dtbs

# ── 5. Copy output ────────────────────────────────────────────────────────────
echo "==> Copying output to dist/boot/"
cp arch/arm64/boot/Image "$OUT/Image"

# Prefer board-specific DTB; fall back to upstream RK3568 EVB
DTB_NAME="rk3566-${BOARD}.dtb"
DTB_UPSTREAM="arch/arm64/boot/dts/rockchip/rk3568-evb1-v10.dtb"
DTB_BOARD="arch/arm64/boot/dts/rockchip/${DTB_NAME}"

if [ -f "$DTB_BOARD" ]; then
  cp "$DTB_BOARD" "$OUT/rk3566.dtb"
  echo "==> Using board DTB: $DTB_NAME"
elif [ -f "$DTB_UPSTREAM" ]; then
  cp "$DTB_UPSTREAM" "$OUT/rk3566.dtb"
  echo "==> Warning: board DTB not found, using upstream fallback: rk3568-evb1-v10.dtb"
else
  echo "==> Error: no suitable DTB found. Add one to kernel/patches/ or check BOARD name."
  exit 1
fi

# ── 6. Build + install kernel modules ─────────────────────────────────────────
MODULES_DIR="$SCRIPT_DIR/.build/rootfs/lib/modules"
mkdir -p "$MODULES_DIR"

echo "==> Building kernel modules"
make -j"$(nproc)" \
  ARCH="$ARCH" \
  CROSS_COMPILE="$CROSS_COMPILE" \
  modules

echo "==> Installing modules to .build/rootfs/"
make ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" \
  INSTALL_MOD_PATH="$SCRIPT_DIR/.build/rootfs" \
  modules_install

echo "==> Kernel build complete"
ls -lh "$OUT/"
