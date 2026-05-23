#!/bin/bash
# scripts/release.sh — full PocketMint release builder
# Usage: ./scripts/release.sh 0.5.0
# Requires: xz, mktorrent, python3, gh (GitHub CLI), git, zip
set -e

VERSION="${1:?Usage: $0 <version>  e.g. $0 0.5.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
IMG_NAME="mintkit-pizero2w-v$VERSION.img"
IMG_XZ="$IMG_NAME.xz"
TORRENT_FILE="mintkit-v$VERSION.torrent"
TRACKER="udp://tracker.opentrackr.org:1337/announce"
WEB_SEED="https://github.com/Crystal-Kitsune-Studios/MintKit/releases/download/v$VERSION/$IMG_XZ"
RELEASE_NOTES="$ROOT/CHANGELOG.md"

echo "==> PocketMint release v$VERSION"
echo ""

# ── 1. Zip all apps ──────────────────────────────────────────────────────────
echo "==> Zipping apps..."
APPS_OUT="$DIST/apps"
mkdir -p "$APPS_OUT"
for app_dir in "$ROOT"/rootfs/apps/*/; do
  app="$(basename "$app_dir")"
  out="$APPS_OUT/$app.zip"
  rm -f "$out"
  (cd "$app_dir" && zip -qr "$out" .)
  echo "    Zipped: $app"
done

# ── 2. Build image ────────────────────────────────────────────────────────────
echo ""
echo "==> Building image..."
BASE_IMG="$DIST/mintkit-pizero2w.img"
VERSIONED_IMG="$DIST/$IMG_NAME"

if [ ! -f "$VERSIONED_IMG" ]; then
  if [ ! -f "$BASE_IMG" ]; then
    sudo -E bash "$ROOT/scripts/build-firmware.sh"
    sudo -E bash "$ROOT/scripts/build-kernel.sh"
    sudo -E bash "$ROOT/scripts/build-image.sh"
  fi
  echo "==> Renaming image to versioned filename..."
  cp "$BASE_IMG" "$VERSIONED_IMG"
else
  echo "    Versioned image already exists, skipping build."
fi

# ── 3. Remove old XZ, generate new XZ ────────────────────────────────────────
echo ""
echo "==> Compressing image..."
rm -f "$DIST"/*.img.xz
xz -9 --keep --threads=0 "$VERSIONED_IMG"
echo "    Created: $DIST/$IMG_XZ"

# ── 4. Checksums ─────────────────────────────────────────────────────────────
echo ""
echo "==> Generating checksums..."
cd "$DIST"
SHA256=$(sha256sum "$IMG_XZ" | awk '{print $1}')
MD5=$(md5sum    "$IMG_XZ" | awk '{print $1}')
echo "    SHA256: $SHA256"
echo "    MD5:    $MD5"
echo "$SHA256  $IMG_XZ" > "$IMG_XZ.sha256"
echo "$MD5  $IMG_XZ"    > "$IMG_XZ.md5"

# ── 5. Generate .torrent ─────────────────────────────────────────────────────
echo ""
echo "==> Creating torrent..."
rm -f "$DIST"/*.torrent
mktorrent \
  -a "$TRACKER" \
  -w "$WEB_SEED" \
  -n "MintKit-v$VERSION-pizero2w" \
  -o "$DIST/$TORRENT_FILE" \
  "$DIST/$IMG_XZ"
echo "    Created: $DIST/$TORRENT_FILE"

# ── 6. Extract info hash + build magnet link ─────────────────────────────────
echo ""
echo "==> Extracting info hash..."
INFO_HASH=$(python3 - "$DIST/$TORRENT_FILE" <<'EOF'
import sys, hashlib

def decode_bencode(data, idx=0):
    if data[idx:idx+1] == b'd':
        idx += 1
        d = {}
        while data[idx:idx+1] != b'e':
            key, idx = decode_bencode(data, idx)
            val, idx = decode_bencode(data, idx)
            d[key] = (val, idx)
        return d, idx + 1
    elif data[idx:idx+1] == b'l':
        idx += 1
        lst = []
        while data[idx:idx+1] != b'e':
            val, idx = decode_bencode(data, idx)
            lst.append(val)
        return lst, idx + 1
    elif data[idx:idx+1] == b'i':
        end = data.index(b'e', idx)
        return int(data[idx+1:end]), end + 1
    else:
        colon = data.index(b':', idx)
        n = int(data[idx:colon])
        start = colon + 1
        return data[start:start+n], start + n

with open(sys.argv[1], "rb") as f:
    raw = f.read()

# Find "4:info" in the raw bytes and hash everything from there to the matching 'e'
info_start = raw.index(b'4:info') + 6
# Re-encode just the info dict by finding its boundaries
_, end = decode_bencode(raw, info_start)
print(hashlib.sha1(raw[info_start:end]).hexdigest().upper())
EOF
)

# ── 7. Update download.html with new checksums + magnet ──────────────────────
echo ""
echo "==> Patching download.html..."
DOWNLOAD_HTML="/var/www/pocketmint/download.html"
# Version string
sed -i "s/v[0-9]\+\.[0-9]\+\.[0-9]\+ &mdash; Raspberry Pi/v$VERSION \&mdash; Raspberry Pi/" "$DOWNLOAD_HTML"
sed -i "s|download/v[0-9.]\+/mintkit|download/v$VERSION/mintkit|g" "$DOWNLOAD_HTML"
sed -i "s|mintkit-v[0-9.]\+\.torrent|mintkit-v$VERSION.torrent|g" "$DOWNLOAD_HTML"
sed -i "s|mintkit-pizero2w-v[0-9.]\+\.img\.xz|$IMG_XZ|g" "$DOWNLOAD_HTML"
# SHA256
sed -i "s|<span class=\"checksum-val\">[a-f0-9]\{64\}</span>|<span class=\"checksum-val\">$SHA256</span>|" "$DOWNLOAD_HTML"
# MD5
sed -i "s|<span class=\"checksum-val\">[a-f0-9]\{32\}</span>|<span class=\"checksum-val\">$MD5</span>|" "$DOWNLOAD_HTML"
# Magnet
ESCAPED_MAGNET=$(printf '%s\n' "$MAGNET" | sed 's/[[\.*^$()+?{|]/\\&/g')
sed -i "s|href=\"magnet:?[^\"]*\"|href=\"$ESCAPED_MAGNET\"|" "$DOWNLOAD_HTML"
echo "    download.html patched"

# ── 8. Commit + tag + push ────────────────────────────────────────────────────
echo ""
echo "==> Committing release..."
cd "$ROOT"
git add download.html
git add -f dist/apps/*.zip 2>/dev/null || true
git commit -m "release: v$VERSION" || echo "    (nothing new to commit)"
git tag -f "v$VERSION"
git push origin main
git push origin "v$VERSION" --force
echo "    Pushed tag v$VERSION"

# ── 9. Create GitHub release ─────────────────────────────────────────────────
echo ""
echo "==> Creating GitHub release..."
RELEASE_BODY="## MintKit v$VERSION

**SHA256:** \`$SHA256\`
**MD5:** \`$MD5\`
**Magnet:** \`$MAGNET\`

### Install
Flash \`$IMG_XZ\` to a microSD card using Raspberry Pi Imager or \`dd\`.
See [download page](https://pocketmint.crystal-kitsune-studios.com/download) for full instructions."

gh release delete "v$VERSION" --yes 2>/dev/null || true
gh release create "v$VERSION" \
  "$DIST/$IMG_XZ" \
  "$DIST/$TORRENT_FILE" \
  "$DIST/$IMG_XZ.sha256" \
  "$DIST/$IMG_XZ.md5" \
  --title "MintKit v$VERSION" \
  --notes "$RELEASE_BODY"
echo "    GitHub release v$VERSION created"

# ── 10. Deploy to server ──────────────────────────────────────────────────────
echo ""
read -p "==> Deploy to server now? [y/N] " DEPLOY
if [[ "$DEPLOY" =~ ^[Yy]$ ]]; then
  bash "$ROOT/scripts/deploy.sh"
fi

echo ""
echo "✅  Release v$VERSION complete!"
echo "    XZ:      $DIST/$IMG_XZ"
echo "    Torrent: $DIST/$TORRENT_FILE"
echo "    SHA256:  $SHA256"
echo "    MD5:     $MD5"
echo "    Magnet:  $MAGNET"