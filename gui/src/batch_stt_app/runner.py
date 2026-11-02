"""Run the core batch in a worker thread and forward progress to the UI thread."""

from __future__ import annotations

import asyncio
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

from batch_stt_mlx.batch import run_batch
from batch_stt_mlx.events import Reporter
from batch_stt_mlx.settings import Settings


class ThreadSafeReporter(Reporter):
    """Re-dispatches every reporter call onto the asyncio (UI) loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, target: Reporter):
        self._loop = loop
        self._target = target

    def _post(self, fn: Callable, *args) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    def log(self, text):
        self._post(self._target.log, text)

    def batch_started(self, pending, skipped):
        self._post(self._target.batch_started, pending, skipped)

    def file_started(self, index, pending, audio, duration):
        self._post(self._target.file_started, index, pending, audio, duration)

    def chunk_done(self, audio, end_secs, duration, text):
        self._post(self._target.chunk_done, audio, end_secs, duration, text)

    def file_done(self, audio, ok):
        self._post(self._target.file_done, audio, ok)

    def batch_done(self, processed, failed, skipped, cancelled):
        self._post(self._target.batch_done, processed, failed, skipped, cancelled)


class KeepAwake:
    """Prevent idle sleep while a batch runs (like `caffeinate -i`)."""

    def __enter__(self):
        self._proc = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
        return self

    def __exit__(self, *exc):
        self._proc.terminate()
        self._proc.wait()


async def run_batch_async(settings: Settings, ui: Reporter, cancel: threading.Event) -> int:
    loop = asyncio.get_running_loop()
    reporter = ThreadSafeReporter(loop, ui)
    with KeepAwake():
        return await loop.run_in_executor(
            None, lambda: run_batch(settings, reporter=reporter, cancel=cancel)
        )


def reveal_in_finder(path: Path) -> None:
    subprocess.run(["/usr/bin/open", str(path)], check=False)
