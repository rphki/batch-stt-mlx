"""Tests for TOML settings loading."""

from pathlib import Path

from batch_stt_mlx.settings import (
    Settings,
    load_settings,
    merge_cli_overrides,
    settings_from_toml,
)


def test_defaults():
    s = Settings()
    assert s.model.startswith("mlx-community/")
    assert s.monitor_chunk_secs == 90.0
    assert s.verbose is False
    assert s.condition_on_previous_text_first is True
    assert s.condition_on_previous_text_retry is False


def test_settings_from_toml_language_null():
    s = settings_from_toml({"language": "", "model": "tiny"})
    assert s.language is None
    assert s.model == "tiny"


def test_settings_from_toml_verbose():
    s = settings_from_toml({"verbose": True})
    assert s.verbose is True


def test_load_settings_file(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "batch-stt.toml"
    cfg.write_text(
        'language = "de"\nrecursive = true\nloop_max_consecutive = 7\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    s = load_settings(directory=tmp_path)
    assert s.language == "de"
    assert s.recursive is True
    assert s.loop_max_consecutive == 7
    assert s.config_path == cfg


def test_cli_overrides(tmp_path: Path):
    s = Settings(language="de", recursive=False)
    s2 = merge_cli_overrides(s, language="en", recursive=True, dry_run=True, verbose=True)
    assert s2.language == "en"
    assert s2.recursive is True
    assert s2.dry_run is True
    assert s2.verbose is True
