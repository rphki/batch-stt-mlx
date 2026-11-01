"""Tests for model download size and free-space helpers (no network)."""

from types import SimpleNamespace

import huggingface_hub

from mlx_whisper_batch.models import free_bytes, missing_bytes


def test_free_bytes_walks_up_to_existing_dir(tmp_path):
    assert free_bytes(tmp_path / "not" / "created" / "yet") > 0


def test_missing_bytes_local_path_is_zero(tmp_path):
    assert missing_bytes(str(tmp_path)) == 0


def test_missing_bytes_sums_files_to_download(monkeypatch):
    def fake_snapshot_download(repo_id, **kwargs):
        assert kwargs["dry_run"] is True
        return [
            SimpleNamespace(file_size=1000, will_download=True),
            SimpleNamespace(file_size=500, will_download=False),
            SimpleNamespace(file_size=20, will_download=True),
        ]

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    assert missing_bytes("org/model") == 1020
