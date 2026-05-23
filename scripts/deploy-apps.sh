#!/bin/bash
# scripts/deploy.sh — deploy all PocketMint server files
set -e

POCKETMINT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DEST="/var/www/pocketmint"

# --- Web pages ---
sudo cp "$POCKETMINT_ROOT/index.html"      "$WEB_DEST/index.html"
sudo cp "$POCKETMINT_ROOT/pocketmall.html" "$WEB_DEST/pocketmall.html"
sudo cp "$POCKETMINT_ROOT/download.html"   "$WEB_DEST/download.html"
echo "Web pages deployed"

# --- Launcher files for OTA ---
LAUNCHER_SRC="$POCKETMINT_ROOT/rootfs/launcher"
LAUNCHER_DEST="$WEB_DEST/launcher"
sudo mkdir -p "$LAUNCHER_DEST"
sudo cp "$LAUNCHER_SRC/mintos.py"  "$LAUNCHER_DEST/"
sudo cp "$LAUNCHER_SRC/updater.py" "$LAUNCHER_DEST/"
echo "Launcher files deployed for OTA"

# --- version.json ---
VERSION="0.5.0"
echo "{\"version\":\"$VERSION\"}" | sudo tee "$WEB_DEST/version.json"
echo "version.json updated to $VERSION"

# --- App zips ---
APPS_DEST="$WEB_DEST/apps"
sudo mkdir -p "$APPS_DEST"
for app in crystal-browser crypt-raid chiptune mintnotes pocketdraw retrocore pixelcraft; do
  APP_DIR="$POCKETMINT_ROOT/rootfs/apps/$app"
  if [ -d "$APP_DIR" ]; then
    (cd "$APP_DIR" && sudo zip -qr "$APPS_DEST/$app.zip" .)
    echo "Deployed app: $app"
  fi
done

# --- Reload nginx ---
sudo nginx -s reload
echo "Done. Site is live."