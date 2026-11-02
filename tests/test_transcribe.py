"""Tests for chunked transcribe + retry (mocked mlx)."""

import pytest

from batch_stt_mlx.settings import Settings
from batch_stt_mlx.transcribe import (
    RepeatLoopDetected,
    transcribe_chunked,
    transcribe_with_retry,
)


def test_chunked_aborts_on_loop():
    calls = []

    def fake(path, **kwargs):
        calls.append(kwargs.get("clip_timestamps"))
        return {
            "text": "x",
            "language": "de",
            "segments": [{"text": "loop"} for _ in range(3)],
        }

    settings = Settings(monitor_chunk_secs=30, loop_max_consecutive=5, max_attempts=1)
    with pytest.raises(RepeatLoopDetected):
        transcribe_chunked(
            "dummy.wav",
            settings,
            condition_on_previous_text=True,
            audio_duration=90,
            transcribe_fn=fake,
        )
    # 3 segments per chunk; aborts once cumulative run hits threshold
    assert 1 <= len(calls) <= 2


def test_retry_switches_condition():
    conditions = []

    def fake(path, **kwargs):
        conditions.append(kwargs.get("condition_on_previous_text"))
        segs = [{"text": "loop"} for _ in range(6)]
        return {"text": "loop", "language": "de", "segments": segs}

    settings = Settings(
        monitor_chunk_secs=120,
        loop_max_consecutive=5,
        max_attempts=2,
        condition_on_previous_text_first=True,
        condition_on_previous_text_retry=False,
    )
    with pytest.raises(RepeatLoopDetected):
        transcribe_with_retry(
            "dummy.wav",
            settings,
            audio_duration=60,
            transcribe_fn=fake,
        )
    assert conditions[0] is True
    assert False in conditions


def test_success_no_loop():
    def fake(path, **kwargs):
        return {
            "text": "hello world",
            "language": "en",
            "segments": [{"text": "hello"}, {"text": "world"}],
        }

    settings = Settings(monitor_chunk_secs=60, max_attempts=2)
    result, attempt = transcribe_with_retry(
        "dummy.wav",
        settings,
        audio_duration=30,
        transcribe_fn=fake,
    )
    assert attempt == 1
    assert result["segments"][0]["text"] == "hello"
    assert result["segments"][1]["text"] == "world"
