#!/usr/bin/env bash
# scripts/deploy-launcher.sh — publish the OTA launcher files to the web server.
#
# WHY THIS FILE EXISTS:
# updater.py fetches its files from
#   https://pocketmint.crystal-kitsune-studios.com/launcher/<file>
# but nothing in this repo ever wrote to that directory. release.sh publishes a
# GitHub release, and OtaManager decides an update exists by comparing the local
# version against the latest GitHub release tag. So tagging a release without
# updating /launcher tells every device "an update is available" and then hands
# them the OLD code. That is how a fixed device un-fixes itself.
#
# Usage: ./scripts/deploy-launcher.sh 1.3.1
#   LAUNCHER_SRC=<dir>  override the source tree (default rootfs/launcher)
#   LAUNCHER_WWW=<dir>  override the destination (default /var/www/pocketmint/launcher)
set -euo pipefail

VERSION="${1:?Usage: $0 <version>  e.g. $0 1.3.1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${LAUNCHER_SRC:-$ROOT/rootfs/launcher}"
WWW="${LAUNCHER_WWW:-/var/www/pocketmint/launcher}"

# Keep this list in sync with LAUNCHER_FILES in updater.py.
FILES=(mintos.py updater.py screenshot.py parental.py settings.py themes.py inputbridge.py battery.py splash.py sleep_timer.py screensaver.py mintcalc.py pisugar.py achievements.py desktop.py friends_ui.py mintshell.py overlay.py savestates.py scores.py sideload.py themes_ui.py mintfb.py sitecustomize.py mintsetup.py)
echo "==> Publishing launcher v$VERSION from $SRC"

# 1. Every file must exist and compile. Serving a launcher with a SyntaxError
#    bricks the UI on every device that pulls it, and the device has no editor.
for f in "${FILES[@]}"; do
  if [ ! -f "$SRC/$f" ]; then
    echo "ERROR: missing $SRC/$f" >&2
    exit 1
  fi
  if ! python3 -m py_compile "$SRC/$f"; then
    echo "ERROR: $f does not compile, refusing to publish" >&2
    exit 1
  fi
done
rm -rf "$SRC/__pycache__"

# 2. The version string in the code must match the version being published, or
#    the device will re-download the same files on every check forever.
if ! grep -q "MintKit $VERSION" "$SRC/mintos.py"; then
  echo "ERROR: $SRC/mintos.py does not contain 'MintKit $VERSION'." >&2
  echo "       Bump the VERSION string before publishing." >&2
  exit 1
fi

# 3. Copy then rename, so a device polling mid-deploy never fetches a half file.
mkdir -p "$WWW"
for f in "${FILES[@]}"; do
  cp "$SRC/$f" "$WWW/$f.incoming"
  mv "$WWW/$f.incoming" "$WWW/$f"
  echo "    published $f"
done

# 4b. Publish launcher assets. Not .py, so they are not in FILES.
ASSETS_SRC="$SRC/assets"
if [ -d "$ASSETS_SRC" ]; then
  mkdir -p "$WWW/assets"
  for a in "$ASSETS_SRC"/*; do
    [ -f "$a" ] || continue
    n="$(basename "$a")"
    cp "$a" "$WWW/assets/$n.incoming"
    mv "$WWW/assets/$n.incoming" "$WWW/assets/$n"
    echo "    published assets/$n"
  done
fi

echo "$VERSION" > "$WWW/version.txt"

# 4. Publish the app files. Nothing in this repo ever wrote to /apps before,
#    which is why a stale app on a device could never heal itself.
APPWWW="${APPS_WWW:-/var/www/pocketmint/apps}"
APP_NAMES=()
for d in "$ROOT"/rootfs/apps/*/; do
  name=$(basename "$d")
  [ -f "$d/main.py" ] || continue
  if ! python3 -m py_compile "$d/main.py"; then
    echo "ERROR: apps/$name/main.py does not compile, refusing to publish" >&2
    exit 1
  fi
  mkdir -p "$APPWWW/$name"
  cp "$d/main.py" "$APPWWW/$name/main.py.incoming"
  mv "$APPWWW/$name/main.py.incoming" "$APPWWW/$name/main.py"
  APP_NAMES+=("$name")
  echo "    published apps/$name/main.py"
done

# 5. Publish the manifest. This is what frees devices from their baked in list.
{
  printf '{\n  "version": "%s",\n  "launcher": [' "$VERSION"
  sep=""
  for f in "${FILES[@]}"; do
    printf '%s"%s"' "$sep" "$f"
    sep=", "
  done
  printf '],\n  "apps": ['
  sep=""
  for name in "${APP_NAMES[@]}"; do
    printf '%s"%s/main.py"' "$sep" "$name"
    sep=", "
  done
  printf ']\n}\n'
} > "$WWW/manifest.json.incoming"
mv "$WWW/manifest.json.incoming" "$WWW/manifest.json"
echo "    published manifest.json"
sync

echo "✅  Launcher v$VERSION published to $WWW"
echo "    Verify: curl -s https://pocketmint.crystal-kitsune-studios.com/launcher/mintos.py | grep -m1 MAX_CLIP"
