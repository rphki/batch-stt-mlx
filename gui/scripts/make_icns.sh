#!/usr/bin/env bash
# Build icons/whisper_batch.icns (macOS app + DMG icon) from the committed PNGs.
# Called by build_dmg.sh; the PNGs come from scripts/make_icon.py.
set -euo pipefail

cd "$(dirname "$0")/.."
SRC="icons/whisper_batch"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
set="$tmp/whisper_batch.iconset"
mkdir "$set"

# iconutil names: icon_<pt>x<pt>[@2x].png, @2x = double pixel size
for pt in 16 32 128 256 512; do
  cp "$SRC-$pt.png" "$set/icon_${pt}x${pt}.png"
  cp "$SRC-$((pt * 2)).png" "$set/icon_${pt}x${pt}@2x.png"
done
iconutil -c icns -o "$SRC.icns" "$set"
