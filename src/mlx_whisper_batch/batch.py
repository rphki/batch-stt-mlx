"""Batch orchestration: scan folder, transcribe, log timings."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from mlx_whisper_batch.audio import (
    audio_duration_secs,
    collect_audio_files,
    format_mmss,
    needs_transcription,
    realtime_factor,
    require_cmd,
)
from mlx_whisper_batch.events import Cancelled, Reporter
from mlx_whisper_batch.outputs import fix_whisper_output_names, remove_outputs, write_result_files
from mlx_whisper_batch.settings import Settings
from mlx_whisper_batch.transcribe import RepeatLoopDetected, transcribe_with_retry


def append_timing_log(
    log_file: Path,
    audio_file: Path,
    audio_mmss: str,
    whisper_mmss: str,
    factor: str,
    *,
    attempt: int | None = None,
    reporter: Reporter | None = None,
) -> None:
    extra = f" attempt={attempt}" if attempt is not None and attempt > 1 else ""
    line = f"{audio_file} {audio_mmss} {whisper_mmss} {factor}{extra}"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    (reporter or Reporter()).log(f"timing: {line}")


def run_batch(
    settings: Settings,
    *,
    reporter: Reporter | None = None,
    cancel: threading.Event | None = None,
) -> int:
    """Transcribe all pending audio files. Returns 0 ok, 1 failures, 2 bad dir, 130 cancelled."""
    reporter = reporter or Reporter()
    log = reporter.log
    directory = settings.directory.resolve()
    if not directory.is_dir():
        log(f"error: not a directory: {directory}")
        return 2

    require_cmd("ffprobe")
    if not settings.dry_run:
        require_cmd("ffmpeg")

    log_file = directory / settings.log_name
    files = collect_audio_files(
        directory,
        recursive=settings.recursive,
        extensions=settings.audio_extensions,
    )

    pending = [a for a in files if needs_transcription(a, force=settings.force)]
    skipped = len(files) - len(pending)
    reporter.batch_started(len(pending), skipped)

    count = 0
    failed = 0
    cancelled = False

    for audio in pending:
        if cancel is not None and cancel.is_set():
            cancelled = True
            break

        count += 1
        try:
            audio_secs = audio_duration_secs(audio)
        except RuntimeError as exc:
            log(f"failed (no ffprobe duration): {audio} ({exc})")
            failed += 1
            reporter.file_done(audio, ok=False)
            continue

        audio_mmss = format_mmss(audio_secs)
        if settings.dry_run:
            log(f"would transcribe: {audio} ({audio_mmss})")
            continue

        log(f"==> [{count}] {audio} ({audio_mmss})")
        reporter.file_started(count, len(pending), audio, audio_secs)
        t0 = time.perf_counter()
        attempt = 1
        try:
            remove_outputs(audio)
            result, attempt = transcribe_with_retry(
                audio,
                settings,
                audio_duration=audio_secs,
                # True → live segments; False → silent (None), not mlx progress bars
                verbose=True if settings.verbose else None,
                reporter=reporter,
                cancel=cancel,
            )
            whisper_secs = time.perf_counter() - t0
            whisper_mmss = format_mmss(whisper_secs)
            factor = realtime_factor(whisper_secs, audio_secs)
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                whisper_mmss,
                factor,
                attempt=attempt,
                reporter=reporter,
            )
            write_result_files(audio, result)
            fix = fix_whisper_output_names(
                audio,
                audio_extensions=settings.audio_extensions,
                log=log,
            )
            txt = audio.with_suffix(".txt")
            if fix.renamed > 0:
                log(f"ok: renamed outputs -> {txt}")
            else:
                log(f"ok: {txt}")
            reporter.file_done(audio, ok=True)
        except Cancelled:
            remove_outputs(audio)
            log(f"cancelled: {audio}")
            count -= 1
            cancelled = True
            break
        except RepeatLoopDetected as exc:
            whisper_secs = time.perf_counter() - t0
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                format_mmss(whisper_secs),
                realtime_factor(whisper_secs, audio_secs),
                attempt=attempt,
                reporter=reporter,
            )
            remove_outputs(audio)
            log(f"failed (repeat loop): {audio}: {exc}")
            failed += 1
            reporter.file_done(audio, ok=False)
        except Exception as exc:  # noqa: BLE001 — batch continues
            whisper_secs = time.perf_counter() - t0
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                format_mmss(whisper_secs),
                realtime_factor(whisper_secs, audio_secs),
                attempt=attempt,
                reporter=reporter,
            )
            log(f"failed: {audio}: {exc}")
            failed += 1
            reporter.file_done(audio, ok=False)

    if settings.dry_run:
        log(f"dry-run: {count} file(s) pending ({skipped} already have .txt)")
        return 0

    verb = "cancelled" if cancelled else "done"
    log(f"{verb}: {count} processed, {failed} failed, {skipped} skipped")
    log(f"timing log: {log_file}")
    reporter.batch_done(count, failed, skipped, cancelled)
    if cancelled:
        return 130
    return 1 if failed else 0
