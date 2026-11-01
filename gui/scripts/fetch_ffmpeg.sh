#!/usr/bin/env bash
# Download static macOS arm64 ffmpeg + ffprobe into the app's resources/bin.
# Source: https://ffmpeg.martin-riedl.de (static builds, no Homebrew dylibs).
#
# Versions and checksums are pinned in scripts/ffmpeg.lock (commit it):
#   fetch_ffmpeg.sh            download the pinned URLs, verify sha256
#   fetch_ffmpeg.sh --update   resolve the latest release and rewrite the lock
# Without a lock file the first run behaves like --update.
set -euo pipefail

cd "$(dirname "$0")/.."
DEST="src/whisper_batch_app/resources/bin"
LOCK="scripts/ffmpeg.lock"
NOTICE="src/whisper_batch_app/resources/licenses/ffmpeg/NOTICE.txt"
LATEST="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release"
TOOLS=(ffmpeg ffprobe)

update=false
[[ "${1:-}" == "--update" || ! -f "$LOCK" ]] && update=true

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$DEST"

locked() {  # locked <tool> <field: 2=url 3=sha256>
  awk -v t="$1" -v f="$2" '$1 == t { print $f }' "$LOCK"
}

new_lock=""
for name in "${TOOLS[@]}"; do
  if $update; then
    # The "latest" link redirects to a versioned URL; pin that one
    url="$(curl -fsSL -r 0-0 -o /dev/null -w '%{url_effective}' "$LATEST/$name.zip")"
  else
    url="$(locked "$name" 2)"
    [[ -n "$url" ]] || { echo "error: $name missing in $LOCK (run with --update)" >&2; exit 1; }
  fi

  curl -fsSL -o "$tmp/$name.zip" "$url"
  sha="$(shasum -a 256 "$tmp/$name.zip" | cut -d' ' -f1)"
  if ! $update && [[ "$sha" != "$(locked "$name" 3)" ]]; then
    echo "error: checksum mismatch for $url" >&2
    echo "  expected $(locked "$name" 3)" >&2
    echo "  got      $sha" >&2
    exit 1
  fi
  new_lock+="$name $url $sha"$'\n'

  unzip -o -q "$tmp/$name.zip" -d "$tmp/$name"
  install -m 755 "$tmp/$name/$name" "$DEST/$name"
done

# Must not link against Homebrew libraries, or the app breaks on clean Macs
if otool -L "$DEST/ffmpeg" "$DEST/ffprobe" | grep -q /opt/homebrew; then
  echo "error: binaries link against /opt/homebrew" >&2
  exit 1
fi

version_info="$("$DEST/ffmpeg" -hide_banner -version)"
config="$(grep '^configuration:' <<< "$version_info")"
# nonfree builds may not be redistributed at all
if grep -q -- '--enable-nonfree' <<< "$config"; then
  echo "error: ffmpeg build uses --enable-nonfree (not redistributable)" >&2
  exit 1
fi

if $update; then
  {
    echo "# Pinned ffmpeg builds for the app bundle. Rewrite with: scripts/fetch_ffmpeg.sh --update"
    echo "# tool url sha256"
    printf '%s' "$new_lock"
  } > "$LOCK"
  echo "wrote $LOCK — review and commit it"
fi

# GPL notice shipped in the app (COPYING.GPLv3 next to it is committed)
version="$(head -1 <<< "$version_info" | sed -E 's/^ffmpeg version ([0-9.]+).*/\1/')"
cat > "$NOTICE" <<EOF
Whisper Batch bundles ffmpeg and ffprobe ${version}. They run as separate
programs and are licensed under the GNU General Public License version 3
(see COPYING.GPLv3 in this folder). Whisper Batch itself is MIT-licensed.

Binaries (static macOS arm64 builds by Martin Riedl):
$(printf '%s' "$new_lock" | awk '{ printf "  %s  %s\n  sha256 %s\n", $1, $2, $3 }')

Corresponding source:
  FFmpeg:           https://ffmpeg.org/releases/ffmpeg-${version}.tar.xz
  Build script:     https://git.martin-riedl.de/ffmpeg/build-script
  Library sources:  linked from https://ffmpeg.martin-riedl.de

Build ${config}
EOF
head -1 <<< "$version_info"
