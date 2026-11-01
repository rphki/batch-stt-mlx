#!/usr/bin/env bash
# Release Whisper Batch: bump the version, test, build the DMG, tag, publish on GitHub.
#
#   gui/scripts/release.sh                 next patch version (0.1.0 -> 0.1.1)
#   gui/scripts/release.sh minor|major     next minor / major version
#   gui/scripts/release.sh --dry-run       everything up to the DMG; nothing is
#                                          committed, tagged or published
#
# Only prerequisite: `gh auth login`. Versions below 1.0.0 are published as pre-releases.
set -euo pipefail

cd "$(dirname "$0")/../.."
REPO_ROOT="$PWD"
VERSION_FILES=(pyproject.toml gui/pyproject.toml src/mlx_whisper_batch/__init__.py)

die() { echo "error: $*" >&2; exit 1; }
warn() { echo "warning: $*" >&2; }

bump=patch
dry_run=false
for arg in "$@"; do
  case "$arg" in
    patch|minor|major) bump="$arg" ;;
    --dry-run) dry_run=true ;;
    *) die "unknown argument '$arg' (usage: release.sh [patch|minor|major] [--dry-run])" ;;
  esac
done

# --- Preflight -----------------------------------------------------------------

[[ -z "$(git status --porcelain)" ]] || die "uncommitted changes — commit or stash them first"

git fetch -q origin
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != main ]]; then
  $dry_run && warn "on branch '$branch' (a real release must run on main)" \
    || die "on branch '$branch' — run: git switch main && git pull"
fi
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  $dry_run && warn "HEAD differs from origin/main (a real release must match it)" \
    || die "local main differs from origin/main — run: git pull (and push your commits first)"
fi

gh auth status >/dev/null 2>&1 || die "GitHub CLI not logged in — run: gh auth login"

read_version() {
  sed -nE 's/^(version|__version__) = "([^"]+)"$/\2/p' "$1" | head -1
}
current="$(read_version "${VERSION_FILES[0]}")"
for f in "${VERSION_FILES[@]}"; do
  v="$(read_version "$f")"
  [[ "$v" == "$current" ]] || die "version mismatch: $f has '$v', ${VERSION_FILES[0]} has '$current'"
done
[[ "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || die "version '$current' is not MAJOR.MINOR.PATCH"

major="${BASH_REMATCH[1]}" minor="${BASH_REMATCH[2]}" patch="${BASH_REMATCH[3]}"
case "$bump" in
  patch) new="$major.$minor.$((patch + 1))" ;;
  minor) new="$major.$((minor + 1)).0" ;;
  major) new="$((major + 1)).0.0" ;;
esac
tag="v$new"
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null || [[ -n "$(git ls-remote --tags origin "$tag")" ]]; then
  die "tag $tag already exists — choose another bump (minor/major)"
fi
echo "release: $current -> $new ($bump)$($dry_run && echo ', dry run')"

# --- Environments (created on first use) ---------------------------------------

find_python() {
  for py in python3.13 python3.12 python3.11 python3; do
    if command -v "$py" >/dev/null && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
      echo "$py"; return
    fi
  done
  die "Python 3.11+ not found — run: brew install python@3.12"
}
if [[ ! -x .venv/bin/pytest || ! -x gui/.venv/bin/briefcase ]]; then
  PY="$(find_python)" || exit 1
fi
if [[ ! -x .venv/bin/pytest ]]; then
  echo "creating .venv (core tests)…"
  "$PY" -m venv .venv
  .venv/bin/pip install -q -e ".[dev]"
fi
if [[ ! -x gui/.venv/bin/briefcase ]]; then
  echo "creating gui/.venv (Briefcase)…"
  "$PY" -m venv gui/.venv
  gui/.venv/bin/pip install -q briefcase
fi

# --- Bump (working tree only; restored on any failure or dry run) ----------------

restore_versions() { git -C "$REPO_ROOT" checkout -q -- "${VERSION_FILES[@]}"; }
trap restore_versions EXIT

sed -i '' -E "s/^version = \"$current\"$/version = \"$new\"/" pyproject.toml gui/pyproject.toml
sed -i '' -E "s/^__version__ = \"$current\"$/__version__ = \"$new\"/" src/mlx_whisper_batch/__init__.py
for f in "${VERSION_FILES[@]}"; do
  [[ "$(read_version "$f")" == "$new" ]] || die "could not set version in $f"
done

# --- Test and build ------------------------------------------------------------

echo "core tests…"
.venv/bin/pytest -q

echo "app tests…"
gui_log="$(mktemp)"
(cd gui && .venv/bin/briefcase dev --test -r --no-input) > "$gui_log" 2>&1 || true
grep -q "Test suite passed" "$gui_log" || { tail -40 "$gui_log" >&2; die "app tests failed"; }

echo "building DMG…"
gui/scripts/build_dmg.sh
built="gui/dist/Whisper Batch-$new.dmg"
[[ -f "$built" ]] || die "expected $built after build"
asset="gui/dist/WhisperBatch-$new-macOS-arm64.dmg"
cp "$built" "$asset"

prerelease=()
[[ "${new%%.*}" == 0 ]] && prerelease=(--prerelease)

if $dry_run; then
  echo
  echo "dry run OK — would publish $tag with $asset${prerelease[0]:+ as pre-release}"
  echo "versions restored to $current; nothing committed, tagged or published"
  exit 0
fi

# --- Publish -------------------------------------------------------------------

# The version commit is created through the GitHub API, so GitHub signs it
# ("Verified"); it is rejected if main moved since the preflight check.
if ! oid="$(gui/scripts/api_commit.sh main "$(git rev-parse HEAD)" "Release $tag" "${VERSION_FILES[@]}")"; then
  die "could not commit the version bump on GitHub (main changed meanwhile?) — run: git pull, then release again"
fi
restore_versions
trap - EXIT
git pull -q --ff-only origin main || warn "could not update local main — run: git pull"

notes="$(mktemp)"
cat > "$notes" <<EOF
## Install

1. Download **WhisperBatch-$new-macOS-arm64.dmg** below, open it and drag **Whisper Batch** into **Applications**.
2. First launch: macOS blocks the app because it is not notarized yet. Open **System Settings → Privacy & Security** and click **Open Anyway** next to the message about Whisper Batch.
3. On the first run the app offers to download the speech model; after that it works offline.

Requires an Apple Silicon Mac with macOS 14 or newer.
EOF

# GitHub creates the tag on exactly that commit
release_cmd=(gh release create "$tag" "$asset" --target "$oid" --title "Whisper Batch $new"
  --generate-notes --notes-file "$notes" ${prerelease[@]+"${prerelease[@]}"})
if ! "${release_cmd[@]}"; then
  echo "error: release commit $oid is on main, but creating the GitHub release failed. Retry with:" >&2
  printf '  %q' "${release_cmd[@]}" >&2
  echo >&2
  exit 1
fi
