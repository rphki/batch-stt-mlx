"""Detect Whisper repeat-loop hallucinations in segment lists."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


def normalize_line(text: str) -> str:
    return " ".join((text or "").strip().split()).casefold()


def segment_texts(segments: Sequence[Mapping[str, Any]]) -> list[str]:
    return [normalize_line(str(seg.get("text") or "")) for seg in segments]


def max_consecutive_run(lines: Sequence[str]) -> tuple[int, str]:
    best_n = 0
    best_line = ""
    current_n = 0
    current_line = ""
    for line in lines:
        if not line:
            current_n = 0
            current_line = ""
            continue
        if line == current_line:
            current_n += 1
        else:
            current_line = line
            current_n = 1
        if current_n > best_n:
            best_n = current_n
            best_line = current_line
    return best_n, best_line


def has_repeat_loop(
    segments: Sequence[Mapping[str, Any]],
    *,
    max_consecutive: int = 5,
    mode_fraction: float = 0.4,
    mode_min_segments: int = 12,
) -> bool:
    """Return True if segments look like a stuck repeat loop."""
    lines = [line for line in segment_texts(segments) if line]
    if not lines:
        return False

    run_n, _ = max_consecutive_run(lines)
    if max_consecutive > 0 and run_n >= max_consecutive:
        return True

    if mode_fraction > 0 and len(lines) >= mode_min_segments:
        _mode, count = Counter(lines).most_common(1)[0]
        if count / len(lines) >= mode_fraction and count >= max_consecutive:
            return True

    return False
