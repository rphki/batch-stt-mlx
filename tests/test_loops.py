"""Tests for repeat-loop detection."""

from batch_stt_mlx.loops import has_repeat_loop, max_consecutive_run, normalize_line


def segs(*texts: str):
    return [{"text": t} for t in texts]


def test_normalize_line():
    assert normalize_line("  Hello   World  ") == "hello world"


def test_no_loop_varied():
    assert not has_repeat_loop(segs("a", "b", "c", "a", "b"), max_consecutive=5)


def test_consecutive_loop():
    texts = ["ok"] + ["same line"] * 5
    assert has_repeat_loop(segs(*texts), max_consecutive=5)


def test_just_under_threshold():
    texts = ["same"] * 4
    assert not has_repeat_loop(segs(*texts), max_consecutive=5)


def test_mode_fraction_loop():
    texts = ["noise", "loop"] * 2 + ["loop"] * 10
    assert has_repeat_loop(
        segs(*texts),
        max_consecutive=5,
        mode_fraction=0.4,
        mode_min_segments=12,
    )


def test_empty_segments():
    assert not has_repeat_loop([])
    assert not has_repeat_loop(segs("", "  ", ""))


def test_max_consecutive_run():
    n, line = max_consecutive_run(["a", "b", "b", "b", "c"])
    assert n == 3
    assert line == "b"
