#!/usr/bin/env bash
# Build, smoke-test and package Whisper Batch.app as an ad-hoc signed DMG.
# Usage: gui/scripts/build_dmg.sh   (expects gui/.venv with briefcase installed)
set -euo pipefail

cd "$(dirname "$0")/.."
BRIEFCASE=".venv/bin/briefcase"
APP="build/whisper_batch_app/macos/app/Whisper Batch.app"
BIN="src/whisper_batch_app/resources/bin"

# Always re-fetch so the bundle contains exactly the builds pinned in ffmpeg.lock
scripts/fetch_ffmpeg.sh
# Briefcase needs the macOS icon as .icns (app and DMG); derived from the committed PNGs
scripts/make_icns.sh

# Start from a fresh bundle: Briefcase writes Info.plist (e.g. the minimum macOS
# version) only when it creates the bundle, so an old build dir keeps stale values
rm -rf build/whisper_batch_app/macos
"$BRIEFCASE" build macOS app -r -u --update-resources --no-input

# macOS must refuse to launch on systems older than the wheels were built for
min_os="$(sed -nE 's/^min_os_version = "([^"]+)"$/\1/p' pyproject.toml)"
plist_min="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist")"
if [[ -z "$min_os" || "$plist_min" != "$min_os" ]]; then
  echo "error: Info.plist LSMinimumSystemVersion is '$plist_min', pyproject.toml says '$min_os'" >&2
  exit 1
fi

# GPL: the bundled ffmpeg must ship with its licence text and source pointer
LICENSES="$APP/Contents/Resources/app/whisper_batch_app/resources/licenses/ffmpeg"
for f in NOTICE.txt COPYING.GPLv3; do
  [[ -s "$LICENSES/$f" ]] || { echo "error: $f missing in app bundle" >&2; exit 1; }
done

# Smoke test: transcribe a generated clip with the bundle, without Homebrew on PATH
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
say -o "$tmp/selftest.aiff" "This is a short self test."
"$BIN/ffmpeg" -loglevel error -i "$tmp/selftest.aiff" "$tmp/selftest.m4a"
rm "$tmp/selftest.aiff"
env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin WHISPER_BATCH_SELFTEST="$tmp" \
  perl -e 'alarm shift; exec {$ARGV[0]} @ARGV or die "exec: $!"' 300 \
  "$APP/Contents/MacOS/Whisper Batch" 2>&1 | grep '^selftest:' || true
if [[ ! -s "$tmp/selftest.txt" ]]; then
  echo "error: bundle self-test produced no transcript" >&2
  exit 1
fi
echo "self-test transcript: $(cat "$tmp/selftest.txt")"

"$BRIEFCASE" package macOS app --adhoc-sign --no-input
ls -lh dist/*.dmg
