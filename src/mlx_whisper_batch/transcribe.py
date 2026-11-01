"""Chunked mlx_whisper transcription with early repeat-loop abort and retry."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from mlx_whisper_batch.events import Cancelled, Reporter
from mlx_whisper_batch.loops import has_repeat_loop
from mlx_whisper_batch.settings import Settings


class RepeatLoopDetected(RuntimeError):
    """Raised when a repeat loop is detected mid-transcription."""


TranscribeFn = Callable[..., dict[str, Any]]


def _default_transcribe(audio: Any, **kwargs: Any) -> dict[str, Any]:
    import mlx_whisper

    return mlx_whisper.transcribe(audio, **kwargs)


def _chunk_bounds(duration: float, chunk_secs: float) -> list[tuple[float, float]]:
    if duration <= 0:
        return [(0.0, 0.0)]
    chunk = max(1.0, float(chunk_secs))
    bounds: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(duration, start + chunk)
        bounds.append((start, end))
        if end >= duration:
            break
        start = end
    return bounds


def _prompt_tail(segments: list[dict[str, Any]], max_chars: int) -> str | None:
    if max_chars <= 0 or not segments:
        return None
    text = " ".join((seg.get("text") or "").strip() for seg in segments).strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[-max_chars:].lstrip()


def _renumber(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        item = dict(seg)
        item["id"] = i
        out.append(item)
    return out


def transcribe_chunked(
    audio: Path | str,
    settings: Settings,
    *,
    condition_on_previous_text: bool,
    audio_duration: float,
    transcribe_fn: TranscribeFn | None = None,
    verbose: bool | None = None,
    reporter: Reporter | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    """Transcribe in time windows; raise RepeatLoopDetected on early loop.

    Default verbose=None silences mlx-whisper (no progress bar, no segment dump).
    Raises Cancelled before the next window once `cancel` is set.
    """
    fn = transcribe_fn or _default_transcribe
    reporter = reporter or Reporter()
    path = str(audio)
    all_segments: list[dict[str, Any]] = []
    language: str | None = settings.language
    full_text_parts: list[str] = []

    for start, end in _chunk_bounds(audio_duration, settings.monitor_chunk_secs):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        kwargs: dict[str, Any] = {
            "path_or_hf_repo": settings.model,
            "condition_on_previous_text": condition_on_previous_text,
            "verbose": verbose,
            "clip_timestamps": [start, end],
        }
        if settings.language:
            kwargs["language"] = settings.language
        prompt = _prompt_tail(all_segments, settings.initial_prompt_chars)
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = fn(path, **kwargs)
        language = result.get("language") or language
        chunk_segments = list(result.get("segments") or [])
        all_segments.extend(chunk_segments)
        chunk_text = (result.get("text") or "").strip()
        if chunk_text:
            full_text_parts.append(chunk_text)
        reporter.chunk_done(Path(path), end, audio_duration, chunk_text)

        if has_repeat_loop(
            all_segments,
            max_consecutive=settings.loop_max_consecutive,
            mode_fraction=settings.loop_mode_fraction,
            mode_min_segments=settings.loop_mode_min_segments,
        ):
            raise RepeatLoopDetected(
                f"repeat loop after chunk {start:.1f}-{end:.1f}s "
                f"({len(all_segments)} segments)"
            )

    text = " ".join(full_text_parts).strip()
    if not text:
        text = " ".join((s.get("text") or "").strip() for s in all_segments).strip()

    return {
        "text": text,
        "segments": _renumber(all_segments),
        "language": language,
    }


def transcribe_with_retry(
    audio: Path | str,
    settings: Settings,
    *,
    audio_duration: float,
    transcribe_fn: TranscribeFn | None = None,
    verbose: bool | None = None,
    reporter: Reporter | None = None,
    cancel: threading.Event | None = None,
) -> tuple[dict[str, Any], int]:
    """
    Attempt 1 with condition_on_previous_text_first; on loop, retry with retry flag.
    Returns (result, attempt_number).
    """
    reporter = reporter or Reporter()
    last_error: Exception | None = None
    for attempt in range(1, max(1, settings.max_attempts) + 1):
        if attempt == 1:
            condition = settings.condition_on_previous_text_first
        else:
            condition = settings.condition_on_previous_text_retry
            reporter.log(
                f"loop detected — retry attempt {attempt} "
                f"(condition_on_previous_text={condition})"
            )
        try:
            result = transcribe_chunked(
                audio,
                settings,
                condition_on_previous_text=condition,
                audio_duration=audio_duration,
                transcribe_fn=transcribe_fn,
                verbose=verbose,
                reporter=reporter,
                cancel=cancel,
            )
            # Final check (should already be clean)
            if has_repeat_loop(
                result.get("segments") or [],
                max_consecutive=settings.loop_max_consecutive,
                mode_fraction=settings.loop_mode_fraction,
                mode_min_segments=settings.loop_mode_min_segments,
            ):
                raise RepeatLoopDetected("repeat loop in completed transcript")
            return result, attempt
        except RepeatLoopDetected as exc:
            last_error = exc
            reporter.log(f"warning: {exc}")
            continue
    assert last_error is not None
    raise last_error
