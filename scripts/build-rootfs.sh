#!/usr/bin/env bash
# scripts/build-rootfs.sh
# Build a minimal Ubuntu Jammy ARM64 rootfs with MintKit launcher + games
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
source "$SCRIPT_DIR/config/mintkit.conf"

ARCH="${ARCH:-arm64}"
BUILD_DIR="$SCRIPT_DIR/.build"
ROOTFS="$BUILD_DIR/rootfs"

USER="${ROOTFS_USER:-mintkit}"
PASS="${ROOTFS_PASSWORD:-mintkit}"
HOST="${ROOTFS_HOSTNAME:-pocketmint}"

mkdir -p "$ROOTFS"

# ── 1. Bootstrap base system ──────────────────────────────────────────────────
if [ ! -f "$ROOTFS/bin/bash" ]; then
  echo "==> Bootstrapping Ubuntu Jammy (arm64) — this takes a few minutes"
  debootstrap \
    --arch=arm64 \
    --foreign \
    --include=ca-certificates,locales,tzdata \
    jammy \
    "$ROOTFS" \
    http://ports.ubuntu.com/ubuntu-ports

  # Second stage inside qemu
  cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/"
  chroot "$ROOTFS" /debootstrap/debootstrap --second-stage
fi

# ── 2. Basic config ───────────────────────────────────────────────────────────
echo "==> Configuring hostname, locale, fstab"
echo "$HOST" > "$ROOTFS/etc/hostname"

cat > "$ROOTFS/etc/hosts" << EOF
127.0.0.1   localhost
127.0.1.1   $HOST
EOF

cat > "$ROOTFS/etc/fstab" << EOF
/dev/mmcblk0p2  /        ext4  defaults,noatime  0 1
/dev/mmcblk0p1  /boot    vfat  defaults          0 2
tmpfs           /tmp     tmpfs defaults,size=64M 0 0
EOF

# ── 3. APT sources + package install ─────────────────────────────────────────
echo "==> Writing APT sources"
cat > "$ROOTFS/etc/apt/sources.list" << EOF
deb http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse
deb http://ports.ubuntu.com/ubuntu-ports jammy-updates main restricted universe multiverse
deb http://ports.ubuntu.com/ubuntu-ports jammy-security main restricted universe multiverse
EOF

echo "==> Installing packages inside chroot"
chroot "$ROOTFS" /bin/bash -c "
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y --no-install-recommends \
    systemd systemd-sysv udev dbus \
    python3 python3-pygame python3-evdev python3-psutil \
    alsa-utils libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 \
    libdrm2 libgbm1 libegl1 libgles2 \
    wpa-supplicant iproute2 iputils-ping wget curl \
    openssh-server sudo nano htop \
    fonts-dejavu-core fontconfig \
    fbset v4l-utils \
    xz-utils bzip2 rsync
  apt-get clean
  rm -rf /var/lib/apt/lists/*
"

# ── 4. Create user ────────────────────────────────────────────────────────────
echo "==> Creating user: $USER"
chroot "$ROOTFS" /bin/bash -c "
  id -u $USER &>/dev/null || useradd -m -s /bin/bash -G sudo,audio,video,input,dialout $USER
  echo '$USER:$PASS' | chpasswd
  echo 'root:root' | chpasswd
"

# ── 5. Copy MintKit launcher + games ─────────────────────────────────────────
echo "==> Installing launcher"
install -Dm755 "$SCRIPT_DIR/rootfs/launcher/mintos.py" \
  "$ROOTFS/home/$USER/mintos.py"

echo "==> Installing bundled games"
cp -r "$SCRIPT_DIR/rootfs/games" "$ROOTFS/home/$USER/games"
chroot "$ROOTFS" chown -R "$USER:$USER" "/home/$USER"

# ── 6. systemd service ────────────────────────────────────────────────────────
echo "==> Installing mintkit systemd service"
install -Dm644 "$SCRIPT_DIR/rootfs/services/mintkit.service" \
  "$ROOTFS/etc/systemd/system/mintkit.service"

chroot "$ROOTFS" /bin/bash -c "
  systemctl enable mintkit.service
  systemctl disable getty@tty1.service 2>/dev/null || true
  systemctl enable ssh
"

# ── 7. udev rules (cartridge + gamepad) ──────────────────────────────────────
echo "==> Installing udev rules"
cp "$SCRIPT_DIR/rootfs/udev/"*.rules \
  "$ROOTFS/etc/udev/rules.d/" 2>/dev/null || true

# ── 8. mintkit.conf ───────────────────────────────────────────────────────────
echo "==> Installing runtime config"
install -Dm644 "$SCRIPT_DIR/config/mintkit.conf" \
  "$ROOTFS/home/$USER/.config/mintkit/mintkit.conf"
chroot "$ROOTFS" chown -R "$USER:$USER" "/home/$USER/.config"

# ── 9. SDL2 / display environment ────────────────────────────────────────────
cat > "$ROOTFS/etc/environment" << EOF
SDL_VIDEODRIVER=kmsdrm
SDL_AUDIODRIVER=alsa
DRM_MASTER_DELAY=1
HOME=/home/$USER
EOF

# ── 10. Network — wpa_supplicant skeleton ────────────────────────────────────
cat > "$ROOTFS/etc/wpa_supplicant/wpa_supplicant.conf" << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US
EOF

cat > "$ROOTFS/etc/systemd/network/10-wlan.network" << EOF
[Match]
Name=wlan0

[Network]
DHCP=yes
EOF

chroot "$ROOTFS" systemctl enable wpa_supplicant systemd-networkd 2>/dev/null || true

# ── 11. Serial console (ttyS2 for RK3566) ────────────────────────────────────
chroot "$ROOTFS" /bin/bash -c "
  mkdir -p /etc/systemd/system/serial-getty@ttyS2.service.d
  systemctl enable serial-getty@ttyS2.service 2>/dev/null || true
"

# ── 12. Locale + timezone ────────────────────────────────────────────────────
chroot "$ROOTFS" /bin/bash -c "
  echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen
  locale-gen
  update-locale LANG=en_US.UTF-8
  ln -sf /usr/share/zoneinfo/UTC /etc/localtime
"

echo "==> Rootfs build complete: $ROOTFS"
du -sh "$ROOTFS"
