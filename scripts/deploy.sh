#!/usr/bin/env bash
# scripts/deploy.sh — deploy built dist files to /var/www/pocketmint
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
WWW="/var/www/pocketmint"

echo "==> Deploying to $WWW"

# App zips
if [ -d "$DIST/apps" ]; then
  mkdir -p "$WWW/apps"
  cp -v "$DIST/apps/"*.zip "$WWW/apps/"
  echo "    App zips deployed."
fi

# Torrent file (served from web root)
if ls "$DIST"/*.torrent 1>/dev/null 2>&1; then
  cp -v "$DIST"/*.torrent "$WWW/"
  echo "    Torrent deployed."
fi

# HTML files (already patched in place by release.sh, but sync from public/ if present)
if [ -d "$ROOT/public" ]; then
  for f in download.html index.html pocketmall.html; do
    [ -f "$ROOT/public/$f" ] && cp -v "$ROOT/public/$f" "$WWW/$f"
  done
  echo "    HTML files synced."
fi

echo "✅  Deploy complete."