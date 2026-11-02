"""Headless UI tests with Toga's dummy backend (no window, no MLX)."""

import asyncio
import json
import os

import pytest

os.environ["TOGA_BACKEND"] = "toga_dummy"

from batch_stt_mlx import batch as batch_mod  # noqa: E402
from batch_stt_mlx.transcribe import transcribe_chunked  # noqa: E402
from batch_stt_app import app as app_mod  # noqa: E402
from batch_stt_app import i18n, runner  # noqa: E402


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "audio"
    d.mkdir()
    for name in ("a.mp3", "b.m4a", "c.wav"):
        (d / name).write_bytes(b"")
    (d / "c.txt").write_text("done\n")
    return d


@pytest.fixture
def app(tmp_path, folder, monkeypatch):
    monkeypatch.setattr(i18n, "LANG", "en")
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"folder": str(folder), "language": "de"}))
    monkeypatch.setattr(app_mod.BatchSTT, "prefs_file", property(lambda self: prefs))
    monkeypatch.setattr(app_mod, "is_model_cached", lambda model: True)
    monkeypatch.setattr(batch_mod, "require_cmd", lambda name: None)
    monkeypatch.setattr(batch_mod, "audio_duration_secs", lambda path: 120.0)
    monkeypatch.setattr(runner.KeepAwake, "__enter__", lambda self: self)
    monkeypatch.setattr(runner.KeepAwake, "__exit__", lambda self, *exc: None)
    return app_mod.BatchSTT(formal_name="BatchSTT", app_id="com.rphki.batch-stt-app-test")


def test_startup_restores_prefs_and_counts_pending(app, folder):
    assert app.folder_label.text == str(folder)
    assert app.language.value == "German"
    assert app.status.text == "2 file(s) to transcribe, 1 already done"
    assert app.start_button.enabled


def test_force_switch_updates_count_and_saves(app):
    app.force.value = True
    assert app.status.text == "3 file(s) to transcribe, 0 already done"
    assert json.loads(app.prefs_file.read_text())["force"] is True


def test_run_writes_outputs_and_reports_progress(app, folder, monkeypatch):
    seen_settings = []

    def fake_retry(audio, settings, **kwargs):
        seen_settings.append(settings)
        kwargs["reporter"].chunk_done(audio, 90.0, 120.0, f"text of {audio.name}")
        return {"text": "hi", "language": "de", "segments": [{"text": f"hi {audio.name}"}]}, 1

    monkeypatch.setattr(batch_mod, "transcribe_with_retry", fake_retry)
    app.loop.run_until_complete(app.on_start(app.start_button))

    assert (folder / "a.txt").read_text() == "hi a.mp3\n"
    assert (folder / "b.txt").read_text() == "hi b.m4a\n"
    assert seen_settings[0].language == "de"
    assert seen_settings[0].verbose is False
    assert app.progress.value == 1.0
    assert app.status.text == "2 transcribed, 0 failed, 1 skipped."
    assert "text of a.mp3" in app.log_view.value
    assert app.start_button.enabled is False  # nothing left to do
    assert app.choose_button.enabled and not app.cancel_button.enabled


def test_cancel_stops_after_current_chunk(app, folder, monkeypatch):
    def fake_retry(audio, settings, **kwargs):
        app.cancel_event.set()  # user pressed Cancel while the first file runs
        return transcribe_chunked(
            audio, settings, condition_on_previous_text=True, audio_duration=120.0,
            transcribe_fn=lambda *a, **k: {"text": "x", "segments": [{"text": "x"}]},
            reporter=kwargs["reporter"], cancel=kwargs["cancel"],
        ), 1

    monkeypatch.setattr(batch_mod, "transcribe_with_retry", fake_retry)
    app.loop.run_until_complete(app.on_start(app.start_button))

    assert not (folder / "a.txt").exists()
    assert app.status.text == "Cancelled. 0 transcribed so far."


def test_german_strings(monkeypatch):
    monkeypatch.setattr(i18n, "LANG", "de")
    assert i18n._("pending", pending=1, skipped=2) == "1 Datei(en) zu transkribieren, 2 bereits erledigt"
    assert set(i18n.STRINGS) == {k for k, v in i18n.STRINGS.items() if {"en", "de"} <= set(v)}


def test_quit_while_idle_is_allowed(app):
    # Toga wraps the overridden method as a handler taking `command`
    assert asyncio.run(app.on_exit(None)) is True


@pytest.fixture
def model_missing(app, monkeypatch):
    """Model not cached, 3 GB to download; records dialogs and download calls."""
    dialogs, downloads = [], []

    async def fake_dialog(dialog):
        dialogs.append(dialog)
        return True  # user confirms

    monkeypatch.setattr(app_mod, "is_model_cached", lambda model: False)
    monkeypatch.setattr(app_mod, "missing_bytes", lambda model: 3_000_000_000)
    monkeypatch.setattr(app_mod, "ensure_model", lambda model, progress: downloads.append(model))
    monkeypatch.setattr(app.main_window, "dialog", fake_dialog)
    return dialogs, downloads


def test_not_enough_disk_space_blocks_download(app, model_missing, monkeypatch):
    dialogs, downloads = model_missing
    monkeypatch.setattr(app_mod, "free_bytes", lambda: 2_000_000_000)

    assert app.loop.run_until_complete(app.download_model_if_needed("org/model")) is False
    assert [type(d).__name__ for d in dialogs] == ["ErrorDialog"]
    assert downloads == []


def test_enough_disk_space_asks_with_size_then_downloads(app, model_missing, monkeypatch):
    dialogs, downloads = model_missing
    monkeypatch.setattr(app_mod, "free_bytes", lambda: 10_000_000_000)

    assert app.loop.run_until_complete(app.download_model_if_needed("org/model")) is True
    assert [type(d).__name__ for d in dialogs] == ["ConfirmDialog"]
    assert downloads == ["org/model"]
