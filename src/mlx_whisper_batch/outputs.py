"""Write transcript outputs and fix mlx_whisper truncated basenames."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from mlx_whisper_batch.audio import is_audio
from mlx_whisper_batch.settings import DEFAULT_AUDIO_EXTENSIONS

OUTPUT_SUFFIXES: tuple[str, ...] = ("txt", "json", "edits.json")


@dataclass
class FixResult:
    renamed: int = 0
    skipped: int = 0


def write_result_files(audio: Path, result: dict[str, Any]) -> tuple[Path, Path]:
    """Write sibling .json and .txt (one stripped segment line each)."""
    json_path = audio.with_suffix(".json")
    txt_path = audio.with_suffix(".txt")
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [(seg.get("text") or "").strip() for seg in result.get("segments") or []]
    txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return json_path, txt_path


def output_base_stem(name: str) -> str:
    if name.endswith(".edits.json"):
        return name[: -len(".edits.json")]
    return Path(name).stem


def is_output_name(name: str) -> bool:
    if name.endswith(".edits.json"):
        return True
    ext = Path(name).suffix.lower().lstrip(".")
    return ext in {"txt", "json"}


def count_audio_prefix_matches(candidate_stem: str, audio_files: Sequence[Path]) -> int:
    count = 0
    for audio in audio_files:
        correct = audio.with_suffix("").name
        if correct.startswith(candidate_stem):
            count += 1
    return count


def find_orphan_output(
    audio: Path,
    suffix: str,
    audio_files: Sequence[Path],
) -> Path | None:
    directory = audio.parent
    correct_stem = audio.with_suffix("").name
    if suffix == "edits.json":
        candidates = sorted(directory.glob("*.edits.json"))
    else:
        candidates = sorted(directory.glob(f"*.{suffix}"))

    best: Path | None = None
    best_len = 0
    for candidate in candidates:
        if not candidate.is_file():
            continue
        name = candidate.name
        if not is_output_name(name):
            continue
        cand_stem = output_base_stem(name)
        if cand_stem == correct_stem:
            continue
        if len(cand_stem) >= len(correct_stem):
            continue
        if not correct_stem.startswith(cand_stem):
            continue
        if count_audio_prefix_matches(cand_stem, audio_files) != 1:
            continue
        if len(cand_stem) > best_len:
            best = candidate
            best_len = len(cand_stem)
    return best


def fix_whisper_output_names(
    audio: Path,
    *,
    dry_run: bool = False,
    audio_extensions: Sequence[str] = DEFAULT_AUDIO_EXTENSIONS,
    log: Callable[[str], None] | None = None,
) -> FixResult:
    log = log or (lambda text: print(text, flush=True))
    directory = audio.parent
    correct_stem = audio.with_suffix("").name
    audio_files = [
        p for p in directory.iterdir() if p.is_file() and is_audio(p, audio_extensions)
    ]
    result = FixResult()

    for suffix in OUTPUT_SUFFIXES:
        right = directory / f"{correct_stem}.{suffix}"
        if right.is_file():
            continue
        orphan = find_orphan_output(audio, suffix, audio_files)
        if orphan is None:
            continue
        if right.exists():
            log(f"skip (target exists): {right}")
            result.skipped += 1
            continue
        if dry_run:
            log(f"would rename: {orphan} -> {right}")
        else:
            orphan.rename(right)
            log(f"renamed: {orphan} -> {right}")
        result.renamed += 1

    return result


def remove_outputs(audio: Path) -> None:
    for path in (audio.with_suffix(".json"), audio.with_suffix(".txt")):
        if path.is_file():
            path.unlink()
