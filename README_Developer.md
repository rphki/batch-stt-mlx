# mlx-whisper-batch — Developer notes

End-user install, config, and overnight usage: see [README.md](README.md).

This file covers local development, tests, and promoting a working tree to the stable pipx CLI.

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
  src/whisper_batch_app/
    __main__.py             # entry; handles `<app> -c CODE` re-launches (multiprocessing)
    app.py                  # window, prefs, model download, bundle self-test
    runner.py               # worker thread, thread-safe reporter, caffeinate
    i18n.py                 # de/en strings
    resources/bin/          # ffmpeg + ffprobe (downloaded, gitignored)
  scripts/fetch_ffmpeg.sh   # static arm64 ffmpeg/ffprobe
  scripts/build_dmg.sh      # fetch ffmpeg, build, self-test without Homebrew, package DMG
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
- **Size:** app ~950 MB, DMG ~230 MB; `torch` (pulled in by mlx-whisper) is ~350 MB of that.
- **Signing:** `build_dmg.sh` signs ad hoc. For notarized releases use a Developer ID: `briefcase package macOS app` without `--adhoc-sign`.
- **ffmpeg licence:** the downloaded static builds are typically GPL. Ship the matching licence text and source pointer with releases, or switch to an LGPL build.

## Promote to pipx

When the editable tree looks good for overnight use:

```bash
deactivate   # optional; pipx does not need the venv
pipx reinstall mlx-whisper-batch
# or from the repo root: pipx install . --force
which whisper-batch   # expect ~/.local/bin/whisper-batch
```

That freezes the current tree into pipx again (`reinstall` uses the package/environment name `mlx-whisper-batch`, not `.` or the CLI name). Further edits stay in the venv until the next reinstall.
