# batch-stt-mlx

**Batch transcription** of dictation archives on **Apple Silicon** using [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).

Built for folders with of MP3, AAC, WAV, 3GA, ... voice recordings from **digital voice recorders** or **phones**: run it overnight, get `.json` + `.txt` next to each audio file. 

Repeat-loop hallucinations are detected **during** transcription (not after 30 minutes of garbage) and retried with safer settings.

> **macOS Apple Silicon only.** This tool depends on MLX. It is not for Linux, Windows, or Intel Macs without MLX support.

**Not a Terminal user?** Use the [Mac app](#mac-app-no-terminal): download, drag to Applications, choose a folder, press Start.

CLI name: `batch-stt` (short). Package / repo name: `batch-stt-mlx`.

Contributors: see [README_Developer.md](README_Developer.md).

Background and motivation (why this exists, local-only, overnight batching) on my website [aporeo.com](https://aporeo.com):

- [English](https://aporeo.com/en/articles/mlx-whisper-batch)
- [Deutsch](https://aporeo.com/de/articles/mlx-whisper-batch)

## Mac app (no Terminal)

**BatchSTT.app** wraps the same transcription in a window: choose a folder, pick language and model, press **Start**. Python, MLX and ffmpeg are bundled; no Homebrew or pipx needed. Requires macOS 14+ on Apple Silicon.

1. Open the [Releases page](https://github.com/rphki/batch-stt-mlx/releases). Under the newest release (at the top), download `BatchSTT-<version>-macOS-arm64.dmg`.
2. Open the DMG and drag **BatchSTT** into **Applications**.
3. First launch: the app is not notarized yet, so macOS blocks it. Open **System Settings → Privacy & Security**, scroll to the message about "BatchSTT" and click **Open Anyway**.
4. On the first run the app offers to download the speech model (~3 GB for best quality). After that it works offline.

The app keeps the Mac awake while transcribing, writes the same `.txt` / `.json` / `batch-stt.log` files as the CLI, and honours a `batch-stt.toml` in the chosen folder (or `~/.rphki/batch-stt.toml`); the options chosen in the window take precedence.

The app bundles ffmpeg (GPL); see **Help → Third-Party Licenses**.

**Uninstall:** move **BatchSTT** from Applications to the Trash. To also free the disk space of the speech models and remove the app's settings, delete `~/.cache/huggingface/hub/models--mlx-community--whisper-*` and `~/Library/Application Support/com.rphki.batch-stt-app` (the models are shared with the CLI).

The rest of this README covers the command-line tool.

## Requirements

- Apple Silicon Mac (M1 or newer)
- [Homebrew](https://brew.sh/)
- Python 3.11+
- `ffmpeg` (includes `ffprobe`)
- [pipx](https://pipx.pypa.io/) (recommended for the CLI) or a venv

No prior Hugging Face account, Whisper install, or MLX setup is required. On a clean machine, the steps below are enough.

## Install Python and ffmpeg

```bash
brew install python@3.12 ffmpeg
python3 --version   # expect 3.11+
ffprobe -version
```

If `python3` is still older than 3.11, use Homebrew’s binary explicitly (e.g. `/opt/homebrew/bin/python3.12`) when creating a venv, or ensure that `python3` points at 3.12.

## Install batch-stt

**No PyPI upload required.** GitHub (or a local clone) is enough.

```bash
brew install pipx
pipx ensurepath   # then open a new terminal if needed

git clone https://github.com/rphki/batch-stt-mlx.git
cd batch-stt-mlx
pipx install .
```

Or without cloning first:

```bash
pipx install git+https://github.com/rphki/batch-stt-mlx.git
```

`pipx install` pulls in `mlx-whisper` and its dependencies (MLX, PyTorch, …) into an isolated environment. After that, `batch-stt` is on your PATH (`~/.local/bin`). No copying into `/usr/local/bin`.

Update after `git pull` (pipx environment name = package name, not `.` and not the CLI name):

```bash
pipx reinstall batch-stt-mlx
```

Or from the repo root: `pipx install . --force`.

## First run: model download

The first transcription downloads the default Whisper model from Hugging Face (`mlx-community/whisper-large-v3-mlx`) into `~/.cache/huggingface`. That needs network, roughly **~3 GB** of disk, and can take several minutes depending on your connection. Later runs reuse the cache.

No Hugging Face login or API token is required for the default (public) model — mlx-whisper fetches it automatically.

## Configuration

Copy the example and edit:

```bash
# to the audio file directory (for dir specific language setting etc.)
cp batch-stt.example.toml batch-stt.toml
# or to vendor dir (global = user-wide):
mkdir -p ~/.rphki
cp batch-stt.example.toml ~/.rphki/batch-stt.toml
```

Search order: `--config PATH` → `./batch-stt.toml` → `~/.rphki/batch-stt.toml`.

CLI flags override the file. Important keys:

| Key | Role                                                                       |
|-----|----------------------------------------------------------------------------|
| `model` | Hugging Face / local mlx-whisper model                                     |
| `language` | e.g. `"de"`; empty / omit = auto-detect                                    |
| `verbose` | `true` = print live transcript segments; default true                      |
| `monitor_chunk_secs` | Window size for early loop checks (default 90)                             |
| `loop_max_consecutive` | Abort if the same line repeats this many times in a row                    |
| `max_attempts` | 1 = first settings only; 2 = retry with `condition_on_previous_text_retry` |
| `condition_on_previous_text_first` / `_retry` | Defaults: `true` / `false`                                                 |

## Usage

```bash
batch-stt /path/to/dictation-archive
batch-stt /path/to/archive --dry-run
batch-stt /path/to/archive --recursive
batch-stt /path/to/archive --force
batch-stt /path/to/archive -m mlx-community/whisper-large-v3-mlx -l de
batch-stt /path/to/archive -v   # live transcript segments
```

Overnight tip (prevent sleep):

```bash
caffeinate -i batch-stt /path/to/archive --recursive
```

Also check **System Settings → Energy** so the Mac does not sleep mid-batch.

### Timing log

Each file appends a line to `<DIR>/batch-stt.log`:

```text
<path> <audio m:ss> <whisper m:ss> <realtime-factor> [attempt=N]
```

`factor` is whisper_seconds / audio_seconds (one decimal). Retries add `attempt=N`.

### Output files

For `interview.m4a`:

- `interview.json` — full mlx-whisper result (segments, etc.)
- `interview.txt` — one stripped segment per line

If mlx ever writes a truncated basename, `batch-stt` renames it. You can also fix a folder later:

```bash
batch-stt-fix-output-names /path/to/folder
batch-stt-fix-output-names /path/to/folder --dry-run
```

## Repeat-loop detection

Whisper can get stuck repeating the same line. This tool:

1. Transcribes in time chunks (`monitor_chunk_secs`)
2. After each chunk, checks for consecutive identical segment lines (and optional dominance of one line)
3. Aborts the rest of the file early
4. Retries with `condition_on_previous_text=false` (default)

Abort latency is about one chunk of Whisper time — not the full recording length.

## Supported formats

Common ffmpeg-backed types: `wav`, `mp3`, `m4a`, `aac`, `flac`, `ogg`, `opus`, `wma`, `aiff`, `caf`, `amr`, `3gp`, `3ga`, plus common video containers.

Proprietary dictation formats (e.g. DSS/DS2) often need conversion first (vendor tools or a specially built ffmpeg). Convert to WAV/M4A before batching.

## Author

Raphael Kirchner [customwebcode.com](https://customwebcode.com)

## License

MIT, see [LICENSE](LICENSE).
