#!/usr/bin/env bash
# install.sh — install PocketMint files onto a running Pi Zero 2 W
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_USER=mintkit
DEST_HOME="/home/$DEST_USER"

echo "==> Installing launcher"
install -Dm755 "$SCRIPT_DIR/rootfs/launcher/mintos.py" \
  "$DEST_HOME/mintos.py"

echo "==> Installing games"
cp -r "$SCRIPT_DIR/rootfs/games/"* "$DEST_HOME/" 2>/dev/null || true
chown -R "$DEST_USER:$DEST_USER" "$DEST_HOME"

echo "==> Installing systemd service"
install -Dm644 \
  "$SCRIPT_DIR/rootfs/etc/systemd/system/mintkit.service" \
  /etc/systemd/system/mintkit.service
systemctl daemon-reload
systemctl enable --now mintkit.service

echo "==> Installing udev rules"
install -Dm644 \
  "$SCRIPT_DIR/rootfs/etc/udev/rules.d/99-mintkit.rules" \
  /etc/udev/rules.d/99-mintkit.rules
udevadm control --reload-rules

echo "==> Done! Reboot or run: systemctl start mintkit"
