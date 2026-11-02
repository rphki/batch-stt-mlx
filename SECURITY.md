# Security policy

batch-stt-mlx and the BatchSTT Mac app transcribe voice recordings locally on the user's machine. Those recordings and their transcripts are often confidential (dictations, interviews, phone calls). We take security issues seriously and appreciate responsible disclosure.

## Supported versions

The project is in pre-release (`0.x`). Only the latest release receives security fixes; fixes are made on `main` and published as a new release.

| Version | Supported |
|---|---|
| latest `0.x` release | yes |
| older releases | no |

The Mac app is signed **ad hoc only** and **not notarized** yet. Download the DMG only from this repository's [releases page](https://github.com/rphki/batch-stt-mlx/releases). The CLI is installed from this repository's source (`pipx install git+https://github.com/rphki/batch-stt-mlx.git`); there is no PyPI package, so a package named `batch-stt-mlx` on PyPI is not ours.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions or pull requests.**

Report them privately through GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, how to reproduce it and its possible impact.

What to expect:

- an acknowledgement within 7 days,
- an assessment and, if confirmed, a plan for a fix,
- credit in the release notes, unless you prefer to stay anonymous.

Please give us reasonable time to fix the issue before disclosing it publicly.

## Scope

Relevant are, for example:

- audio, transcripts or file paths being sent over the network, which the tool must never do (the only intended network access is downloading the Whisper model from Hugging Face),
- code execution, crashes, hangs or excessive resource use caused by crafted audio files or a crafted `batch-stt.toml`,
- the tool writing, renaming or deleting files outside the chosen folder, or overwriting files other than its own `.json` / `.txt` / `batch-stt.log` outputs,
- known vulnerabilities in the components bundled into the Mac app (Python, MLX, PyTorch, ffmpeg) that affect the released DMG,
- weaknesses in the release pipeline or the published artifacts.

Not in scope:

- vulnerabilities in mlx-whisper, MLX, ffmpeg or Hugging Face themselves that do not depend on how this project uses or bundles them (please report those upstream),
- transcription errors or hallucinated text,
- the Gatekeeper warning on first launch, which is expected while the app is not notarized (see [README.md](README.md#mac-app-no-terminal)).

## How the project handles security

- Transcription runs entirely on the device; after the model has been downloaded, the tool works offline.
- The bundled ffmpeg / ffprobe builds are pinned by URL and SHA-256 in [`gui/scripts/ffmpeg.lock`](gui/scripts/ffmpeg.lock); `fetch_ffmpeg.sh` rejects mismatching downloads and `--enable-nonfree` builds.
- Releases are built and tested on a GitHub-hosted runner from `main` by the [release workflow](.github/workflows/release.yml), which uses no secrets besides its own token (`contents: write`). Each build runs the core and app tests and a self-test of the bundled app without Homebrew before anything is published.
- The release commit is created through the GitHub API, so it is signed by GitHub and shows as **Verified**. Details in [README_Developer.md](README_Developer.md#release).
