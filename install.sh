#!/usr/bin/env bash
# install.sh — one-command installer
# Transforms a fresh Armbian/Ubuntu Jammy ARM64 install into MintKit OS
# Run as root: sudo bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER="mintkit"

echo "===================================="
echo " MintKit OS Installer"
echo "===================================="

[ "$EUID" -ne 0 ] && { echo "Run as root: sudo bash install.sh"; exit 1; }

# 1. Packages
echo "==> Installing runtime packages"
apt-get update -q
apt-get install -y --no-install-recommends \
  python3 python3-pygame python3-evdev python3-psutil \
  alsa-utils libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 \
  libdrm2 libgbm1 libegl1 libgles2 \
  wpa-supplicant iproute2 fonts-dejavu-core fontconfig
apt-get clean

# 2. User
echo "==> Creating user $USER"
id -u $USER &>/dev/null || \
  useradd -m -s /bin/bash -G sudo,audio,video,input,dialout $USER
echo "$USER:$USER" | chpasswd

# 3. Launcher + games
echo "==> Installing launcher"
install -Dm755 "$SCRIPT_DIR/rootfs/launcher/mintos.py" /home/$USER/mintos.py
cp -r "$SCRIPT_DIR/rootfs/games" /home/$USER/games
chown -R $USER:$USER /home/$USER

# 4. Config
mkdir -p /home/$USER/.config/mintkit
[ -f "$SCRIPT_DIR/config/mintkit.conf" ] && \
  install -Dm644 "$SCRIPT_DIR/config/mintkit.conf" \
  /home/$USER/.config/mintkit/mintkit.conf
chown -R $USER:$USER /home/$USER/.config

# 5. SDL2 environment
cat > /etc/environment << 'EOF'
SDL_VIDEODRIVER=kmsdrm
SDL_AUDIODRIVER=alsa
EOF

# 6. systemd service
install -Dm644 "$SCRIPT_DIR/rootfs/services/mintkit.service" \
  /etc/systemd/system/mintkit.service
systemctl daemon-reload
systemctl enable mintkit.service
systemctl disable getty@tty1.service 2>/dev/null || true

# 7. udev rules
cp "$SCRIPT_DIR/rootfs/udev/"*.rules /etc/udev/rules.d/ 2>/dev/null || true
udevadm control --reload-rules

echo "==> Done. Reboot to launch MintKit."
