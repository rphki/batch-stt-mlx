# mlx-whisper-batch — Developer notes

End-user install, config, and overnight usage: see [README.md](README.md).

This file covers local development, tests, promoting a working tree to the stable pipx CLI, the Mac app, and releases.

## Requirements (dev)

Same as users: Apple Silicon, `ffmpeg` / `ffprobe`, Python 3.11+. Plus a clone of this repo.

## Develop and test in parallel

Keep a **stable** pipx install for overnight jobs, and a **venv** for development:

```bash
cd mlx-whisper-batch

# stable CLI (frozen copy inside pipx)
pipx install .

# editable Dev env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
whisper-batch --dry-run /path/to/folder   # uses working tree
deactivate

# overnight still uses pipx until you promote:
whisper-batch /path/to/archive
# when happy:
pipx reinstall mlx-whisper-batch
```

With the venv activated, its `bin/` wins over `~/.local/bin`. Check with `which whisper-batch` if unsure.

Shortcut (one install always tracks the working tree): `pipx install --editable .` — convenient, but overnight will run unfinished edits.

## Editable install only

If you do not need a separate overnight pipx copy:

```bash
cd mlx-whisper-batch
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`whisper-batch` and `whisper-fix-output-names` then resolve to the working tree.

## Tests

```bash
source .venv/bin/activate   # if not already
pytest
```

Pytest is configured in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`). Dev extra: `pip install -e ".[dev]"` (pulls in `pytest>=8`).

Mac app UI tests (headless, Toga dummy backend; setup in [Mac app](#mac-app-gui)):

```bash
cd gui && .venv/bin/briefcase dev --test
```

## Package layout

```text
src/mlx_whisper_batch/
  cli.py          # whisper-batch entry
  fix_cli.py      # whisper-fix-output-names entry
  batch.py        # folder scan, orchestration, timing log
  transcribe.py   # chunked mlx-whisper + retry
  loops.py        # repeat-loop heuristics
  outputs.py      # .json / .txt write + truncated-name fix
  audio.py        # duration / format helpers
  settings.py     # TOML + CLI overrides
  events.py       # Reporter (progress hooks) + Cancelled
  models.py       # model cache check + download with progress
tests/            # pytest suite
whisper-batch.example.toml
pyproject.toml    # hatchling, scripts, optional [dev]
```

Entry points (from `pyproject.toml`):

- `whisper-batch` → `mlx_whisper_batch.cli:main`
- `whisper-fix-output-names` → `mlx_whisper_batch.fix_cli:main`

## Mac app (`gui/`)

A [Briefcase](https://briefcase.readthedocs.io/) + [Toga](https://toga.readthedocs.io/) app that depends on the core package via `requires = ["../"]` in `gui/pyproject.toml`. The core reports progress through `mlx_whisper_batch.events.Reporter` and supports cancellation via a `threading.Event`; the CLI uses the printing default.

```text
gui/
  pyproject.toml            # Briefcase config (macOS arm64 only, min macOS 14)
  icons/whisper_batch-*.png # app icon, 16–1024 px (from scripts/make_icon.py; .icns is generated)
  src/whisper_batch_app/
    __main__.py             # entry; handles `<app> -c CODE` re-launches (multiprocessing)
    app.py                  # window, prefs, model download, bundle self-test
    runner.py               # worker thread, thread-safe reporter, caffeinate
    i18n.py                 # de/en strings
    resources/bin/          # ffmpeg + ffprobe (downloaded, gitignored)
    resources/licenses/     # ffmpeg GPLv3 text (committed) + NOTICE.txt (generated)
  scripts/fetch_ffmpeg.sh   # static arm64 ffmpeg/ffprobe, pinned in scripts/ffmpeg.lock (--update to bump)
  scripts/make_icon.py      # renders the icon PNGs (needs Pillow; only when the design changes)
  scripts/make_icns.sh      # PNGs -> icons/whisper_batch.icns via iconutil (run by build_dmg.sh)
  scripts/build_dmg.sh      # fetch ffmpeg, make .icns, build, self-test without Homebrew, package DMG
  scripts/release.sh        # bump version, test, build, tag, publish GitHub release
  tests/                    # headless UI tests (toga-dummy)
```

```bash
cd gui
python3.12 -m venv .venv && .venv/bin/pip install briefcase
.venv/bin/briefcase dev            # run from source
.venv/bin/briefcase dev --test     # UI tests
scripts/build_dmg.sh               # → gui/dist/Whisper Batch-<version>.dmg
```

Notes:

- **Self-test of a built bundle:** `WHISPER_BATCH_SELFTEST=<folder> "build/whisper_batch_app/macos/app/Whisper Batch.app/Contents/MacOS/Whisper Batch"` transcribes the folder with `whisper-tiny` and prints `selftest:` lines to stderr (normal stdout goes to the unified log via `std-nslog`).
- **`sys.executable` is the app stub** in the bundle. Libraries that re-launch Python with `-c` (multiprocessing's resource tracker, used via tqdm) would start a second app; `__main__.py` runs such `-c` code instead. Keep that guard.
- **min macOS 14:** with a lower `min_os_version` pip resolves an older MLX release.
- **Size:** app ~950 MB, DMG ~280 MB; `torch` (pulled in by mlx-whisper) is ~350 MB of the app.
- **Signing:** `build_dmg.sh` signs ad hoc. For notarized releases use a Developer ID: `briefcase package macOS app` without `--adhoc-sign`.
- **ffmpeg licence:** the bundled builds are GPLv3. `fetch_ffmpeg.sh` writes `NOTICE.txt` (version, pinned URLs and checksums, build configuration, links to the corresponding source) next to the committed `COPYING.GPLv3` and refuses `--enable-nonfree` builds; `build_dmg.sh` fails if either file is missing from the bundle. Nothing to do by hand.

## Release

**Normal way: label the PR.** Before merging a PR into `main`, give it one of these labels; the merge then triggers the [Release workflow](.github/workflows/release.yml), which runs `gui/scripts/release.sh` on an Apple Silicon runner and publishes the DMG:

| Label | New version |
|-------|-------------|
| `release` | 0.1.0 → 0.1.1 |
| `release:minor` | 0.1.0 → 0.2.0 |
| `release:major` | 0.1.0 → 1.0.0 |

PRs without a label publish nothing. Progress and errors: **Actions → Release**. To test the pipeline without publishing: **Actions → Release → Run workflow** (dry run is preselected; the built DMG is attached to the run for 7 days).

**Locally**, the same script runs with one command on an up-to-date `main`:

```bash
gui/scripts/release.sh            # 0.1.0 -> 0.1.1
gui/scripts/release.sh minor      # 0.1.0 -> 0.2.0
gui/scripts/release.sh major      # 0.1.0 -> 1.0.0
gui/scripts/release.sh --dry-run  # everything up to the DMG, nothing published
```

Only prerequisite: the GitHub CLI is logged in (`gh auth login`). The script tells you what to do if anything else is off. It:

1. checks: on `main`, no uncommitted changes, same commit as `origin/main`, version identical in `pyproject.toml`, `gui/pyproject.toml` and `src/mlx_whisper_batch/__init__.py`, new tag still free;
2. creates `.venv` / `gui/.venv` if missing;
3. sets the new version in those three files, runs core and app tests, then `build_dmg.sh` (pinned ffmpeg, licence check, bundle self-test without Homebrew);
4. only then commits "Release vX.Y.Z", tags it, pushes `main` and the tag together, and creates the GitHub release with `WhisperBatch-X.Y.Z-macOS-arm64.dmg`, install instructions and generated notes.

Any failure before step 4 restores the version files. Versions below 1.0.0 are published as pre-releases, so link users to the Releases page, not `/releases/latest` (which skips pre-releases).

## Promote to pipx

When the editable tree looks good for overnight use:

```bash
deactivate   # optional; pipx does not need the venv
pipx reinstall mlx-whisper-batch
# or from the repo root: pipx install . --force
which whisper-batch   # expect ~/.local/bin/whisper-batch
```

That freezes the current tree into pipx again (`reinstall` uses the package/environment name `mlx-whisper-batch`, not `.` or the CLI name). Further edits stay in the venv until the next reinstall.
