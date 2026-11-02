"""Tests for output rename helpers."""

from pathlib import Path

from batch_stt_mlx.outputs import (
    find_orphan_output,
    fix_whisper_output_names,
    write_result_files,
)


def test_write_result_files(tmp_path: Path):
    audio = tmp_path / "talk.m4a"
    audio.write_bytes(b"")
    result = {
        "text": "Hello world",
        "segments": [{"text": " Hello "}, {"text": "world"}],
        "language": "en",
    }
    json_path, txt_path = write_result_files(audio, result)
    assert json_path.is_file()
    assert txt_path.read_text(encoding="utf-8") == "Hello\nworld\n"


def test_fix_truncated_orphan(tmp_path: Path):
    audio = tmp_path / "meeting.notes.m4a"
    audio.write_bytes(b"")
    orphan = tmp_path / "meeting.json"
    orphan.write_text('{"segments":[]}\n', encoding="utf-8")

    result = fix_whisper_output_names(audio)
    assert result.renamed == 1
    assert (tmp_path / "meeting.notes.json").is_file()
    assert not orphan.exists()


def test_find_orphan_ambiguous(tmp_path: Path):
    a1 = tmp_path / "meeting.a.m4a"
    a2 = tmp_path / "meeting.b.m4a"
    a1.write_bytes(b"")
    a2.write_bytes(b"")
    orphan = tmp_path / "meeting.json"
    orphan.write_text("{}", encoding="utf-8")
    assert find_orphan_output(a1, "json", [a1, a2]) is None
