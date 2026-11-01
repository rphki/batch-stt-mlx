#!/usr/bin/env bash
# Download static macOS arm64 ffmpeg + ffprobe into the app's resources/bin.
# Source: https://ffmpeg.martin-riedl.de (static builds, no Homebrew dylibs).
# Pin checksums after verifying a download: set FFMPEG_SHA256 / FFPROBE_SHA256.
set -euo pipefail

cd "$(dirname "$0")/.."
DEST="src/whisper_batch_app/resources/bin"
BASE="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release"
FFMPEG_SHA256="${FFMPEG_SHA256:-}"
FFPROBE_SHA256="${FFPROBE_SHA256:-}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$DEST"

fetch() {
  local name="$1" expected="$2"
  curl -fsSL -o "$tmp/$name.zip" "$BASE/$name.zip"
  local actual
  actual="$(shasum -a 256 "$tmp/$name.zip" | cut -d' ' -f1)"
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    echo "error: checksum mismatch for $name.zip ($actual)" >&2
    exit 1
  fi
  echo "$name.zip sha256: $actual"
  unzip -o -q "$tmp/$name.zip" -d "$tmp/$name"
  install -m 755 "$tmp/$name/$name" "$DEST/$name"
}

fetch ffmpeg "$FFMPEG_SHA256"
fetch ffprobe "$FFPROBE_SHA256"

# Must not link against Homebrew libraries, or the app breaks on clean Macs
if otool -L "$DEST/ffmpeg" "$DEST/ffprobe" | grep -q /opt/homebrew; then
  echo "error: binaries link against /opt/homebrew" >&2
  exit 1
fi
"$DEST/ffmpeg" -hide_banner -version | head -1
