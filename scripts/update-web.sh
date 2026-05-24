#!/bin/bash
# scripts/release.sh — full PocketMint release builder
# Usage: ./scripts/release.sh 1.0.0
# Requires: xz, mktorrent, python3, gh (GitHub CLI), git, zip
set -e

VERSION="${1:?Usage: $0 <version>  e.g. $0 1.0.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
IMG_NAME="mintkit-pizero2w-v$VERSION.img"
IMG_XZ="$IMG_NAME.xz"
TORRENT_FILE="mintkit-v$VERSION.torrent"
TRACKER="udp://tracker.opentrackr.org:1337/announce"
WEB_SEED="https://github.com/Crystal-Kitsune-Studios/MintKit/releases/download/v$VERSION/$IMG_XZ"
RELEASE_NOTES="$ROOT/CHANGELOG.md"
REL_DATE="$(date '+%-d %B %Y')"

echo "==> PocketMint release v$VERSION  ($REL_DATE)"
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
        idx += 1; d = {}
        while data[idx:idx+1] != b'e':
            key, idx = decode_bencode(data, idx)
            val, idx = decode_bencode(data, idx)
            d[key] = (val, idx)
        return d, idx + 1
    elif data[idx:idx+1] == b'l':
        idx += 1; lst = []
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
info_start = raw.index(b'4:info') + 6
_, end = decode_bencode(raw, info_start)
print(hashlib.sha1(raw[info_start:end]).hexdigest().upper())
EOF
)
MAGNET="magnet:?xt=urn:btih:${INFO_HASH}&dn=MintKit-v${VERSION}-pizero2w&tr=${TRACKER}&ws=${WEB_SEED}"
echo "    Magnet: $MAGNET"

# ── 7. Update download.html ───────────────────────────────────────────────────
echo ""
echo "==> Patching download.html..."
DOWNLOAD_HTML="/var/www/pocketmint/download.html"
# Version + date subtitle
sed -i "s/v[0-9]\+\.[0-9]\+\.[0-9]\+ &mdash; Raspberry Pi Zero 2 W &mdash; [^<]*/v$VERSION \&mdash; Raspberry Pi Zero 2 W \&mdash; $REL_DATE/" "$DOWNLOAD_HTML"
# Download link filenames
sed -i "s|download/v[0-9.]\+/mintkit|download/v$VERSION/mintkit|g" "$DOWNLOAD_HTML"
sed -i "s|mintkit-v[0-9.]\+\.torrent|mintkit-v$VERSION.torrent|g" "$DOWNLOAD_HTML"
sed -i "s|mintkit-pizero2w-v[0-9.]\+\.img\.xz|$IMG_XZ|g" "$DOWNLOAD_HTML"
sed -i "s|MINTKIT-PIZERO2W-V[0-9A-Z.]\+\.IMG\.XZ|MINTKIT-PIZERO2W-V${VERSION}.IMG.XZ|g" "$DOWNLOAD_HTML"
# SHA256 + MD5
sed -i "s|<span class=\"checksum-val\">[a-f0-9]\{64\}</span>|<span class=\"checksum-val\">$SHA256</span>|" "$DOWNLOAD_HTML"
sed -i "s|<span class=\"checksum-val\">[a-f0-9]\{32\}</span>|<span class=\"checksum-val\">$MD5</span>|"   "$DOWNLOAD_HTML"
# Magnet link
ESCAPED_MAGNET=$(printf '%s\n' "$MAGNET" | sed 's/[[\.*^$()+?{|]/\\&/g')
sed -i "s|href=\"magnet:?[^\"]*\"|href=\"$ESCAPED_MAGNET\"|" "$DOWNLOAD_HTML"
echo "    download.html patched"

# ── 8. Update index.html (Download button version) ───────────────────────────
echo "==> Patching index.html..."
INDEX_HTML="/var/www/pocketmint/index.html"
sed -i "s|Download MintKit v[0-9]\+\.[0-9]\+\.[0-9]\+|Download MintKit v$VERSION|g" "$INDEX_HTML"
echo "    index.html patched"

# ── 9. Regenerate pocketmall.html app grid ───────────────────────────────────
echo "==> Regenerating pocketmall.html..."
export SCRIPT_DIR="$ROOT"
python3 - <<'PYEOF'
import json, os, re, sys
from pathlib import Path

ROOT      = Path(os.environ["SCRIPT_DIR"])
APPS_DIR  = ROOT / "rootfs" / "apps"
MALL_HTML = Path("/var/www/pocketmint/pocketmall.html")

if not MALL_HTML.exists():
    print(f"  WARN: {MALL_HTML} not found — skipping."); sys.exit(0)

apps = []
for gj in sorted(APPS_DIR.glob("*/game.json")):
    try:
        apps.append(json.loads(gj.read_text()))
    except Exception as e:
        print(f"  WARN: {gj}: {e}")

ICONS = {
    "crystal-browser": "&#127760;", "crypt-raid": "&#9876;",
    "pixelcraft": "&#127959;",      "chiptune": "&#127925;",
    "retrocore": "&#127918;",       "pocketdraw": "&#128444;",
    "mintnotes": "&#128221;",       "mintcalc": "&#129518;",
    "mintdocs": "&#128196;",        "mintcam": "&#128247;",
    "pocketcast": "&#127911;",
}

def href(a): return f"/purchase?app={a['id']}" if a.get('price',0) else f"/apps/{a['id']}.zip"
def cats(a): return f"{a.get('category','app')} {'paid' if a.get('price',0) else 'free'}"
def plab(p): return "FREE" if not p else f"${p:.2f}"

rows = []
for a in apps:
    dl  = " download" if not a.get('price',0) else ""
    pc  = " paid" if a.get('price',0) else ""
    rows.append(
        f'    <a href="{href(a)}" class="grid-app" data-cat="{cats(a)}"{dl}>\n'
        f'      <div class="grid-icon">{ICONS.get(a["id"],"&#127873;")}</div>\n'
        f'      <div class="grid-info"><div class="grid-name">{a["name"]}</div>'
        f'<div class="grid-dev">{a["developer"]} &middot; {a.get("category","app").capitalize()}</div></div>\n'
        f'      <div class="grid-price{pc}">{plab(a.get("price",0))}</div>\n'
        f'    </a>'
    )

total = len(apps)
free  = sum(1 for a in apps if not a.get('price',0))
devs  = len(set(a.get('developer','') for a in apps))

html  = MALL_HTML.read_text()
new_g = '  <div class="grid" id="app-grid">\n' + '\n'.join(rows) + '\n  </div>'
html  = re.sub(r'<div class="grid" id="app-grid">.*?</div>', new_g, html, flags=re.DOTALL)
html  = re.sub(r'(<div class="stat-num">)\d+(</div><div class="stat-lbl">Titles)', rf'\g<1>{total}\2', html)
html  = re.sub(r'(<div class="stat-num">)\d+(</div><div class="stat-lbl">Developers)', rf'\g<1>{devs}\2', html)
html  = re.sub(r'(<div class="stat-num">)\d+(</div><div class="stat-lbl">Free)', rf'\g<1>{free}\2', html)
MALL_HTML.write_text(html)
print(f"  pocketmall.html: {total} apps, {devs} devs, {free} free.")
PYEOF
echo "    pocketmall.html patched"

# ── 10. Commit + tag + push ───────────────────────────────────────────────────
echo ""
echo "==> Committing release..."
cd "$ROOT"
git add public/download.html public/index.html public/pocketmall.html 2>/dev/null || true
git add -f dist/apps/*.zip 2>/dev/null || true
git commit -m "release: v$VERSION" || echo "    (nothing new to commit)"
git tag -f "v$VERSION"
git push origin main
git push origin "v$VERSION" --force
echo "    Pushed tag v$VERSION"

# ── 11. Create GitHub release ─────────────────────────────────────────────────
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

# ── 12. Deploy to server ──────────────────────────────────────────────────────
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