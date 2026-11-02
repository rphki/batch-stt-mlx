"""batch-stt-fix-output-names CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from batch_stt_mlx.audio import collect_audio_files
from batch_stt_mlx.outputs import fix_whisper_output_names
from batch_stt_mlx.settings import DEFAULT_AUDIO_EXTENSIONS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch-stt-fix-output-names",
        description=(
            "Rename mlx_whisper outputs truncated at the first dot or by length "
            "so they match the audio basename."
        ),
    )
    p.add_argument("directory", nargs="?", default=".", help="Folder to scan (default: .)")
    p.add_argument("-n", "--dry-run", action="store_true", help="Show planned renames only")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", flush=True)
        return 2

    audio_files = collect_audio_files(
        directory,
        recursive=False,
        extensions=DEFAULT_AUDIO_EXTENSIONS,
    )
    total_renamed = 0
    total_skipped = 0
    for audio in audio_files:
        result = fix_whisper_output_names(audio, dry_run=args.dry_run)
        total_renamed += result.renamed
        total_skipped += result.skipped

    verb = "would rename" if args.dry_run else "renamed"
    print(
        f"{'dry-run: ' if args.dry_run else 'done: '}{verb} {total_renamed} output file(s), "
        f"skip {total_skipped} conflict(s), {len(audio_files)} audio file(s) scanned",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
