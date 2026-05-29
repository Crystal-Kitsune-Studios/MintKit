#!/usr/bin/env bash
# scripts/build-rootfs.sh — build minimal Debian rootfs for PocketMint
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BUILD_DIR="$SCRIPT_DIR/.build"
ROOTFS="$BUILD_DIR/rootfs"
LAUNCHER_SRC="$SCRIPT_DIR/rootfs/launcher/mintos.py"
GAME_SRC="$SCRIPT_DIR/rootfs/games"

mkdir -p "$ROOTFS"

echo "==> Bootstrapping Debian (bookworm) for arm64"
debootstrap --arch=arm64 --foreign \
  --components=main,contrib,non-free,non-free-firmware \
  bookworm "$ROOTFS" http://deb.debian.org/debian

cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/"
chroot "$ROOTFS" /debootstrap/debootstrap --second-stage

# Write apt sources with non-free-firmware before installing packages
cat > "$ROOTFS/etc/apt/sources.list" <<'EOF'
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
deb http://archive.raspberrypi.com/debian/ bookworm main
EOF

echo "==> Adding Raspberry Pi apt repo"
# Import RPi apt repo signing key (must be dearmored — apt requires binary .gpg)
wget -qO- https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
  | gpg --dearmor > "$ROOTFS/etc/apt/trusted.gpg.d/raspberrypi-archive-stable.gpg"

# Add RPi repo to sources (after existing sources.list write below)

echo "==> Installing packages"
chroot "$ROOTFS" apt-get update -qq
chroot "$ROOTFS" apt-get install -y --no-install-recommends \
  python3 python3-pygame python3-pip \
  fbset psmisc openssh-server \
  firmware-brcm80211 wpasupplicant \
  sudo \
  alsa-utils \
  udev systemd-sysv \
  raspberrypi-kernel

echo "==> Configuring hostname & users"
echo "pocketmint" > "$ROOTFS/etc/hostname"
chroot "$ROOTFS" useradd -m -s /bin/bash mintkit
echo "mintkit:mintkit" | chroot "$ROOTFS" chpasswd
mkdir -p "$ROOTFS/etc/sudoers.d"
echo "mintkit ALL=(ALL) NOPASSWD:ALL" >> "$ROOTFS/etc/sudoers.d/mintkit"
chmod 440 "$ROOTFS/etc/sudoers.d/mintkit"

echo "==> Serial console (serial0 / ttyAMA0)"
chroot "$ROOTFS" systemctl enable serial-getty@ttyAMA0.service

echo "==> Copying launcher"
install -Dm755 "$LAUNCHER_SRC" "$ROOTFS/home/mintkit/mintos.py"

echo "==> Copying games"
cp -r "$GAME_SRC"/* "$ROOTFS/home/mintkit/" 2>/dev/null || true

echo "==> Installing systemd service"
install -Dm644 "$SCRIPT_DIR/rootfs/etc/systemd/system/mintkit.service" \
  "$ROOTFS/etc/systemd/system/mintkit.service"
chroot "$ROOTFS" systemctl enable mintkit.service

echo "==> Installing udev rules"
install -Dm644 "$SCRIPT_DIR/rootfs/etc/udev/rules.d/99-mintkit.rules" \
  "$ROOTFS/etc/udev/rules.d/99-mintkit.rules"

echo "==> Configuring wlan0 (ifupdown)"
mkdir -p "$ROOTFS/etc/network/interfaces.d"
cat > "$ROOTFS/etc/network/interfaces.d/wlan0" <<'EOF'
auto wlan0
iface wlan0 inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
EOF

echo "==> Masking conflicting wpa_supplicant.service"
ln -sf /dev/null "$ROOTFS/etc/systemd/system/wpa_supplicant.service"

echo "==> Fetching Pi Zero 2W WiFi firmware (CYW43436S)"
# Try bookworm branch first, fall back to master
FWBASE_BOOKWORM="https://raw.githubusercontent.com/RPi-Distro/firmware-nonfree/refs/heads/bookworm/debian/config/brcm80211/brcm"
FWBASE_MASTER="https://raw.githubusercontent.com/RPi-Distro/firmware-nonfree/master/debian/config/brcm80211/brcm"
mkdir -p "$ROOTFS/lib/firmware/brcm"

for FW in \
    "brcmfmac43436s-sdio.bin" \
    "brcmfmac43436s-sdio.clm_blob" \
    "brcmfmac43436s-sdio.raspberrypi,model-zero-2-w.txt"; do
  OUT="$ROOTFS/lib/firmware/brcm/$FW"
  if wget -q --timeout=30 -O "$OUT" "$FWBASE_BOOKWORM/$FW" 2>/dev/null; then
    echo "  Fetched (bookworm): $FW"
  elif wget -q --timeout=30 -O "$OUT" "$FWBASE_MASTER/$FW" 2>/dev/null; then
    echo "  Fetched (master): $FW"
  else
    echo "  WARN: could not fetch $FW — WiFi firmware may be missing" >&2
    rm -f "$OUT"
  fi
done

echo "==> Rootfs build complete: $ROOTFS"