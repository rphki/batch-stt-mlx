"""whisper-batch CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from mlx_whisper_batch import __version__
from mlx_whisper_batch.audio import MissingDependencyError
from mlx_whisper_batch.batch import run_batch
from mlx_whisper_batch.settings import find_config_file, load_settings, merge_cli_overrides


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="whisper-batch",
        description=(
            "Batch-transcribe dictation archives with mlx-whisper on Apple Silicon. "
            "Writes sibling .json and .txt; aborts early on repeat loops and retries."
        ),
    )
    p.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Folder to scan (default: current directory)",
    )
    p.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="TOML config path (default: ./whisper-batch.toml or ~/.rphki/whisper-batch.toml)",
    )
    p.add_argument("-r", "--recursive", action="store_true", help="Include subdirectories")
    p.add_argument("-n", "--dry-run", action="store_true", help="List files that would be transcribed")
    p.add_argument("-f", "--force", action="store_true", help="Transcribe even if .txt exists")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print live transcript segments (mlx-whisper verbose)",
    )
    p.add_argument("-m", "--model", default=None, help="mlx-whisper model id or path")
    p.add_argument("-l", "--language", default=None, help="Language code (e.g. de); omit for auto")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    directory = Path(args.directory)
    settings = load_settings(config=args.config, directory=directory)
    settings = merge_cli_overrides(
        settings,
        model=args.model,
        language=args.language,
        recursive=True if args.recursive else None,
        force=True if args.force else None,
        dry_run=True if args.dry_run else None,
        verbose=True if args.verbose else None,
    )
    cfg = settings.config_path or find_config_file(args.config)
    if cfg:
        print(f"config: {cfg}", flush=True)
    try:
        return run_batch(settings)
    except MissingDependencyError as exc:
        print(f"error: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
