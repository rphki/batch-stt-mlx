"""Audio discovery and ffprobe duration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence


class MissingDependencyError(RuntimeError):
    """A required external command (ffmpeg / ffprobe) is not on PATH."""


def require_cmd(name: str) -> None:
    if shutil.which(name) is None:
        raise MissingDependencyError(f"'{name}' not found in PATH")


def is_audio(path: Path, extensions: Sequence[str]) -> bool:
    ext = path.suffix.lower().lstrip(".")
    return bool(ext) and ext in {e.lower().lstrip(".") for e in extensions}


def txt_path_for(audio: Path) -> Path:
    return audio.with_suffix(".txt")


def json_path_for(audio: Path) -> Path:
    return audio.with_suffix(".json")


def needs_transcription(audio: Path, *, force: bool) -> bool:
    return force or not txt_path_for(audio).is_file()


def collect_audio_files(
    directory: Path,
    *,
    recursive: bool,
    extensions: Sequence[str],
) -> list[Path]:
    directory = directory.resolve()
    if recursive:
        candidates: Iterable[Path] = (p for p in directory.rglob("*") if p.is_file())
    else:
        candidates = (p for p in directory.iterdir() if p.is_file())
    files = [p for p in candidates if is_audio(p, extensions)]
    files.sort(key=lambda p: str(p).lower())
    return files


def audio_duration_secs(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            "--",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}")
    text = (result.stdout or "").strip()
    if not text or text == "N/A":
        raise RuntimeError(f"no ffprobe duration for {path}")
    return float(text)


def format_mmss(secs: float) -> str:
    total = max(0, int(round(secs)))
    return f"{total // 60}:{total % 60:02d}"


def realtime_factor(whisper_secs: float, audio_secs: float) -> str:
    if audio_secs <= 0:
        return "n/a"
    return f"{whisper_secs / audio_secs:.1f}"
