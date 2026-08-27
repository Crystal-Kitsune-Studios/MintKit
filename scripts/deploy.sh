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

# OTA launcher files.
# updater.py fetches mintos.py and updater.py from $WWW/launcher/, but nothing
# in this repo ever wrote there. A GitHub release therefore announced an update
# while the server kept serving the old code. Publishing is now explicit.
if [ -n "${LAUNCHER_VERSION:-}" ]; then
  bash "$ROOT/scripts/deploy-launcher.sh" "$LAUNCHER_VERSION"
else
  echo "    Launcher publish SKIPPED. Set LAUNCHER_VERSION=x.y.z to publish OTA files."
fi

# HTML files.
# WARNING: release.sh patches the /var/www copies IN PLACE (version, date,
# checksums, magnet link) but only ever git-adds public/*.html, which it never
# writes to. Copying public/ over /var/www therefore REVERTS a fresh release
# back to whatever stale version is committed. Opt in only once public/ is
# genuinely the source of truth.
if [ "${DEPLOY_HTML:-0}" = "1" ] && [ -d "$ROOT/public" ]; then
  for f in download.html index.html pocketmall.html; do
    # Guarded with if, not '&&'. Under set -e a failing '[ -f ]' test as the
    # last statement in the loop body aborts the whole deploy.
    if [ -f "$ROOT/public/$f" ]; then
      cp -v "$ROOT/public/$f" "$WWW/$f"
    fi
  done
  echo "    HTML files synced from public/."
else
  echo "    HTML sync SKIPPED. Set DEPLOY_HTML=1 to overwrite the live pages from public/."
fi

echo "✅  Deploy complete."
