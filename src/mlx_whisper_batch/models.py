"""Model cache check and download with byte progress (for the GUI's first run)."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable

ProgressFn = Callable[[int, int], None]


def is_model_cached(model: str, *, cache_dir: Path | None = None) -> bool:
    """True if `model` is a local path or a complete snapshot in the HF cache."""
    if Path(model).exists():
        return True
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        snapshot_download(model, cache_dir=cache_dir, local_files_only=True)
    except LocalEntryNotFoundError:
        return False
    return True


def missing_bytes(model: str, *, cache_dir: Path | None = None) -> int:
    """Bytes still to download for `model` (0 if local or fully cached). Needs network."""
    if Path(model).exists():
        return 0
    from huggingface_hub import snapshot_download

    plan = snapshot_download(model, cache_dir=cache_dir, dry_run=True)
    return sum(f.file_size for f in plan if f.will_download)


def free_bytes(cache_dir: Path | None = None) -> int:
    """Free disk space where the HF cache lives (or would be created)."""
    if cache_dir is None:
        from huggingface_hub import constants

        cache_dir = Path(constants.HF_HUB_CACHE)
    path = Path(cache_dir)
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free


def _dir_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for p in path.iterdir():
        try:
            total += p.stat().st_size
        except OSError:
            pass  # renamed from .incomplete while scanning
    return total


def ensure_model(
    model: str,
    progress: ProgressFn | None = None,
    *,
    cache_dir: Path | None = None,
    poll_secs: float = 0.5,
) -> Path:
    """Download `model` into the HF cache if needed; return its snapshot path.

    `progress(done_bytes, total_bytes)` is called from a polling thread, measured
    by the growth of the repo's blob folder (works for plain and xet downloads).
    """
    if Path(model).exists():
        return Path(model)
    from huggingface_hub import snapshot_download

    plan = snapshot_download(model, cache_dir=cache_dir, dry_run=True)
    todo = [f for f in plan if f.will_download]
    total = sum(f.file_size for f in todo)
    if not todo or progress is None:
        return Path(snapshot_download(model, cache_dir=cache_dir))

    # <cache>/models--org--name/snapshots/<rev>/<file> → <cache>/models--org--name/blobs
    blobs = Path(todo[0].local_path).parents[2] / "blobs"
    baseline = _dir_bytes(blobs)
    stop = threading.Event()

    def poll() -> None:
        while not stop.wait(poll_secs):
            progress(min(_dir_bytes(blobs) - baseline, total), total)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    try:
        path = Path(snapshot_download(model, cache_dir=cache_dir))
    finally:
        stop.set()
        poller.join()
    progress(total, total)
    return path
