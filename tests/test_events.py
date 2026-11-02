"""Tests for reporter events, cancellation and missing ffmpeg."""

import threading
from pathlib import Path

import pytest

from batch_stt_mlx import batch as batch_mod
from batch_stt_mlx import cli
from batch_stt_mlx.events import Cancelled, Reporter
from batch_stt_mlx.settings import Settings
from batch_stt_mlx.transcribe import transcribe_chunked


class Recorder(Reporter):
    def __init__(self):
        self.lines = []
        self.events = []

    def log(self, text):
        self.lines.append(text)

    def batch_started(self, pending, skipped):
        self.events.append(("batch_started", pending, skipped))

    def file_started(self, index, pending, audio, duration):
        self.events.append(("file_started", index, audio.name))

    def chunk_done(self, audio, end_secs, duration, text):
        self.events.append(("chunk_done", end_secs, text))

    def file_done(self, audio, ok):
        self.events.append(("file_done", audio.name, ok))

    def batch_done(self, processed, failed, skipped, cancelled):
        self.events.append(("batch_done", processed, failed, skipped, cancelled))


def fake_ok(path, **kwargs):
    start, end = kwargs["clip_timestamps"]
    return {"text": f"t{int(end)}", "language": "de", "segments": [{"text": f"t{int(end)}"}]}


def test_chunk_done_per_window():
    rec = Recorder()
    transcribe_chunked(
        "dummy.wav",
        Settings(monitor_chunk_secs=30),
        condition_on_previous_text=True,
        audio_duration=70,
        transcribe_fn=fake_ok,
        reporter=rec,
    )
    assert rec.events == [("chunk_done", 30, "t30"), ("chunk_done", 60, "t60"), ("chunk_done", 70, "t70")]


def test_cancel_between_chunks():
    cancel = threading.Event()
    calls = []

    def fake(path, **kwargs):
        calls.append(kwargs["clip_timestamps"])
        cancel.set()
        return fake_ok(path, **kwargs)

    with pytest.raises(Cancelled):
        transcribe_chunked(
            "dummy.wav",
            Settings(monitor_chunk_secs=30),
            condition_on_previous_text=True,
            audio_duration=90,
            transcribe_fn=fake,
            cancel=cancel,
        )
    assert len(calls) == 1


@pytest.fixture
def audio_dir(tmp_path, monkeypatch):
    for name in ("a.mp3", "b.mp3", "c.mp3"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "c.txt").write_text("done\n")
    monkeypatch.setattr(batch_mod, "require_cmd", lambda name: None)
    monkeypatch.setattr(batch_mod, "audio_duration_secs", lambda path: 60.0)
    return tmp_path


def test_run_batch_events(audio_dir, monkeypatch):
    def fake_retry(audio, settings, **kwargs):
        kwargs["reporter"].chunk_done(Path(audio), 60.0, 60.0, "hi")
        return {"text": "hi", "language": "de", "segments": [{"text": "hi"}]}, 1

    monkeypatch.setattr(batch_mod, "transcribe_with_retry", fake_retry)
    rec = Recorder()
    code = batch_mod.run_batch(Settings(directory=audio_dir), reporter=rec)

    assert code == 0
    assert rec.events[0] == ("batch_started", 2, 1)
    assert ("file_started", 1, "a.mp3") in rec.events
    assert ("file_done", "b.mp3", True) in rec.events
    assert rec.events[-1] == ("batch_done", 2, 0, 1, False)
    assert (audio_dir / "a.txt").read_text() == "hi\n"
    assert any(line.startswith("done: 2 processed") for line in rec.lines)


def test_run_batch_cancel_mid_file(audio_dir, monkeypatch):
    cancel = threading.Event()

    def fake_retry(audio, settings, **kwargs):
        cancel.set()
        raise Cancelled()

    monkeypatch.setattr(batch_mod, "transcribe_with_retry", fake_retry)
    rec = Recorder()
    code = batch_mod.run_batch(Settings(directory=audio_dir), reporter=rec, cancel=cancel)

    assert code == 130
    assert rec.events[-1] == ("batch_done", 0, 0, 1, True)
    assert not (audio_dir / "a.txt").exists()
    assert not (audio_dir / "b.txt").exists()


def test_cli_missing_ffprobe(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("batch_stt_mlx.audio.shutil.which", lambda name: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main([str(tmp_path)]) == 2
    assert "error: 'ffprobe' not found in PATH" in capsys.readouterr().out
