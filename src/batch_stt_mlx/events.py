"""Progress reporting for batch runs (CLI prints, GUI overrides)."""

from __future__ import annotations

from pathlib import Path


class Cancelled(Exception):
    """Raised when a batch run is cancelled between chunks or files."""


class Reporter:
    """Receives batch progress. The defaults print the CLI output lines.

    Subclasses (e.g. the GUI) override `log` to redirect text and the
    structured hooks to drive progress displays.
    """

    def log(self, text: str) -> None:
        print(text, flush=True)

    def batch_started(self, pending: int, skipped: int) -> None:
        pass

    def file_started(self, index: int, pending: int, audio: Path, duration: float) -> None:
        pass

    def chunk_done(self, audio: Path, end_secs: float, duration: float, text: str) -> None:
        pass

    def file_done(self, audio: Path, ok: bool) -> None:
        pass

    def batch_done(self, processed: int, failed: int, skipped: int, cancelled: bool) -> None:
        pass
