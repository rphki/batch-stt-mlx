"""
Batch transcription of dictation archives on Apple Silicon
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import toga
from toga.style.pack import COLUMN, ROW, Pack

from mlx_whisper_batch.audio import MissingDependencyError, collect_audio_files, needs_transcription
from mlx_whisper_batch.events import Reporter
from mlx_whisper_batch.models import ensure_model, free_bytes, is_model_cached, missing_bytes
from mlx_whisper_batch.settings import Settings, load_settings
from whisper_batch_app.i18n import _
from whisper_batch_app.runner import run_batch_async, reveal_in_finder

LANGUAGES = ["auto", "de", "en", "fr", "es", "it"]
MODELS = {
    "mlx-community/whisper-large-v3-mlx": "model_large",
    "mlx-community/whisper-large-v3-turbo": "model_turbo",
    "mlx-community/whisper-small-mlx": "model_small",
}
# Headroom beyond the model download itself (transcripts, temp files, the OS)
DISK_MARGIN = 1_000_000_000


def bundled_bin_dir() -> Path:
    return Path(__file__).parent / "resources" / "bin"


def ffmpeg_notice() -> Path:
    return Path(__file__).parent / "resources" / "licenses" / "ffmpeg" / "NOTICE.txt"


def use_bundled_ffmpeg() -> None:
    """Put bundled ffmpeg/ffprobe first on PATH (core and mlx-whisper call them by name)."""
    bin_dir = bundled_bin_dir()
    if bin_dir.is_dir():
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def build_settings(folder: Path, prefs: dict) -> Settings:
    """Folder TOML (or ~/.rphki global) as base, GUI choices on top."""
    folder_config = folder / "whisper-batch.toml"
    return load_settings(
        config=folder_config if folder_config.is_file() else None,
        directory=folder,
        overrides={
            "model": prefs["model"],
            "language": prefs["language"],
            "recursive": prefs["recursive"],
            "force": prefs["force"],
            "verbose": False,
        },
    )


def format_gb(n: int) -> str:
    return f"{n / 1e9:.1f} GB"


def run_selftest(folder: str) -> None:
    """Headless smoke test of the built bundle: WHISPER_BATCH_SELFTEST=<folder>."""
    import shutil

    from mlx_whisper_batch.batch import run_batch

    class StderrReporter(Reporter):
        # std-nslog redirects sys.stdout to the unified log; write to the real stderr
        def log(self, text):
            os.write(2, f"selftest: {text}\n".encode())

    reporter = StderrReporter()
    reporter.log(f"ffmpeg={shutil.which('ffmpeg')} ffprobe={shutil.which('ffprobe')}")
    model = os.environ.get("WHISPER_BATCH_SELFTEST_MODEL", "mlx-community/whisper-tiny-mlx")
    settings = load_settings(directory=Path(folder), overrides={"model": model, "force": True, "verbose": False})
    try:
        code = run_batch(settings, reporter=reporter)
    except Exception as exc:  # noqa: BLE001
        reporter.log(f"failed: {exc!r}")
        code = 1
    reporter.log(f"exit={code}")
    os._exit(code)


class UiReporter(Reporter):
    """Applies batch progress to the window; called on the UI thread."""

    def __init__(self, app: WhisperBatch):
        self.app = app
        self.pending = 0
        self.index = 0

    def log(self, text):
        self.app.append_log(text)

    def batch_started(self, pending, skipped):
        self.pending = pending
        self.app.progress.value = 0

    def file_started(self, index, pending, audio, duration):
        self.index = index
        self.app.status.text = _("file_progress", index=index, pending=pending, name=audio.name)
        self._set_progress(0.0)

    def chunk_done(self, audio, end_secs, duration, text):
        if text:
            self.app.append_log(text)
        self._set_progress(end_secs / duration if duration > 0 else 1.0)

    def file_done(self, audio, ok):
        self._set_progress(1.0)

    def _set_progress(self, file_fraction: float) -> None:
        if self.pending:
            self.app.progress.value = (self.index - 1 + file_fraction) / self.pending

    def batch_done(self, processed, failed, skipped, cancelled):
        if cancelled:
            self.app.status.text = _("cancelled", processed=processed)
        else:
            self.app.status.text = _("done", processed=processed, failed=failed, skipped=skipped)
            self.app.progress.value = 1.0


class WhisperBatch(toga.App):
    def startup(self):
        use_bundled_ffmpeg()
        if selftest := os.environ.get("WHISPER_BATCH_SELFTEST"):
            run_selftest(selftest)

        self.prefs = self.load_prefs()
        self.folder: Path | None = Path(self.prefs["folder"]) if self.prefs.get("folder") else None
        if self.folder is not None and not self.folder.is_dir():
            self.folder = None
        self.cancel_event: threading.Event | None = None

        self.choose_button = toga.Button(_("choose_folder"), on_press=self.on_choose)
        self.folder_label = toga.Label("", style=Pack(flex=1, margin_left=8))

        self.language = toga.Selection(
            items=[_(f"lang_{code}") for code in LANGUAGES],
            value=_(f"lang_{self.prefs['language']}"),
            on_change=self.on_options_changed,
        )
        self.model = toga.Selection(
            items=[_(key) for key in MODELS.values()],
            value=_(MODELS[self.prefs["model"]]),
            on_change=self.on_options_changed,
        )
        self.recursive = toga.Switch(_("recursive"), value=self.prefs["recursive"], on_change=self.on_options_changed)
        self.force = toga.Switch(_("force"), value=self.prefs["force"], on_change=self.on_options_changed)

        self.start_button = toga.Button(_("start"), on_press=self.on_start, style=Pack(width=120))
        self.cancel_button = toga.Button(_("cancel"), on_press=self.on_cancel, enabled=False, style=Pack(width=120))
        self.finder_button = toga.Button(_("show_in_finder"), on_press=self.on_show_in_finder)

        self.status = toga.Label("")
        self.progress = toga.ProgressBar(max=1.0, style=Pack(flex=1))
        self.log_view = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))

        label_style = Pack(width=90)
        content = toga.Box(
            children=[
                toga.Box(children=[self.choose_button, self.folder_label], style=Pack(direction=ROW, align_items="center")),
                toga.Box(children=[toga.Label(_("language"), style=label_style), self.language], style=Pack(direction=ROW, align_items="center")),
                toga.Box(children=[toga.Label(_("model"), style=label_style), self.model], style=Pack(direction=ROW, align_items="center")),
                toga.Box(children=[self.recursive, self.force], style=Pack(direction=ROW, gap=16)),
                toga.Divider(),
                toga.Box(children=[self.start_button, self.cancel_button, toga.Box(style=Pack(flex=1)), self.finder_button], style=Pack(direction=ROW, gap=8)),
                self.status,
                self.progress,
                self.log_view,
            ],
            style=Pack(direction=COLUMN, margin=16, gap=10),
        )

        if ffmpeg_notice().is_file():
            self.commands.add(toga.Command(self.on_show_licenses, _("licenses"), group=toga.Group.HELP))

        self.main_window = toga.MainWindow(title=self.formal_name, size=(720, 560))
        self.main_window.content = content
        self.main_window.show()
        self.refresh_pending()

    # Preferences -----------------------------------------------------------

    @property
    def prefs_file(self) -> Path:
        return self.paths.config / "prefs.json"

    def load_prefs(self) -> dict:
        prefs = {
            "folder": None,
            "language": "auto",
            "model": "mlx-community/whisper-large-v3-mlx",
            "recursive": False,
            "force": False,
        }
        try:
            prefs.update(json.loads(self.prefs_file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        if prefs["language"] not in LANGUAGES:
            prefs["language"] = "auto"
        if prefs["model"] not in MODELS:
            prefs["model"] = "mlx-community/whisper-large-v3-mlx"
        return prefs

    def save_prefs(self) -> None:
        self.prefs.update(
            folder=str(self.folder) if self.folder else None,
            language=LANGUAGES[[_(f"lang_{c}") for c in LANGUAGES].index(self.language.value)],
            model=list(MODELS)[[_(k) for k in MODELS.values()].index(self.model.value)],
            recursive=self.recursive.value,
            force=self.force.value,
        )
        try:
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            self.prefs_file.write_text(json.dumps(self.prefs, indent=2), encoding="utf-8")
        except OSError:
            pass

    # UI helpers ------------------------------------------------------------

    def append_log(self, text: str) -> None:
        self.log_view.value = (self.log_view.value + "\n" + text) if self.log_view.value else text
        self.log_view.scroll_to_bottom()

    def set_running(self, running: bool) -> None:
        for widget in (self.choose_button, self.language, self.model, self.recursive, self.force, self.start_button):
            widget.enabled = not running
        self.cancel_button.enabled = running
        if not running:
            # Keep the run summary visible; only re-evaluate whether Start makes sense
            self.refresh_pending(update_status=False)

    def refresh_pending(self, *, update_status: bool = True) -> int:
        self.finder_button.enabled = self.folder is not None
        if self.folder is None:
            self.folder_label.text = _("no_folder")
            if update_status:
                self.status.text = ""
            self.start_button.enabled = False
            return 0
        self.folder_label.text = str(self.folder)
        settings = build_settings(self.folder, self.prefs)
        files = collect_audio_files(self.folder, recursive=settings.recursive, extensions=settings.audio_extensions)
        pending = sum(1 for f in files if needs_transcription(f, force=settings.force))
        if update_status:
            self.status.text = _("pending", pending=pending, skipped=len(files) - pending)
        self.start_button.enabled = pending > 0
        return pending

    # Handlers --------------------------------------------------------------

    async def on_choose(self, widget):
        path = await self.main_window.dialog(toga.SelectFolderDialog(_("choose_folder"), initial_directory=self.folder))
        if path is None:
            return
        self.folder = Path(path)
        self.save_prefs()
        self.refresh_pending()

    def on_options_changed(self, widget):
        if not hasattr(self, "progress"):
            return  # still building the window
        self.save_prefs()
        self.refresh_pending()

    def on_show_in_finder(self, widget):
        if self.folder is not None:
            reveal_in_finder(self.folder)

    def on_show_licenses(self, command, **kwargs):
        # Opens the folder with NOTICE.txt and COPYING.GPLv3 in Finder
        reveal_in_finder(ffmpeg_notice().parent)

    def on_cancel(self, widget):
        if self.cancel_event is not None:
            self.cancel_event.set()
            self.cancel_button.enabled = False
            self.status.text = _("cancelling")

    async def on_start(self, widget):
        if self.folder is None:
            return
        self.save_prefs()
        if self.refresh_pending() == 0:
            await self.main_window.dialog(toga.InfoDialog(_("done_title"), _("nothing_to_do")))
            return
        settings = build_settings(self.folder, self.prefs)
        self.log_view.value = ""
        self.set_running(True)
        try:
            if not await self.download_model_if_needed(settings.model):
                return
            self.cancel_event = threading.Event()
            await run_batch_async(settings, UiReporter(self), self.cancel_event)
        except MissingDependencyError as exc:
            await self.main_window.dialog(toga.ErrorDialog(_("error_title"), str(exc)))
        except Exception as exc:  # noqa: BLE001 — keep the app alive and show what happened
            self.append_log(f"error: {exc!r}")
            await self.main_window.dialog(toga.ErrorDialog(_("error_title"), str(exc)))
        finally:
            self.cancel_event = None
            self.set_running(False)

    async def download_model_if_needed(self, model: str) -> bool:
        if await self.loop.run_in_executor(None, is_model_cached, model):
            return True
        try:
            needed = await self.loop.run_in_executor(None, missing_bytes, model)
        except Exception as exc:  # noqa: BLE001 — offline, Hugging Face unreachable
            await self.main_window.dialog(toga.ErrorDialog(_("download_failed"), str(exc)))
            return False
        free = free_bytes()
        if free < needed + DISK_MARGIN:
            await self.main_window.dialog(
                toga.ErrorDialog(
                    _("disk_title"),
                    _("disk_message", needed=format_gb(needed + DISK_MARGIN), free=format_gb(free)),
                )
            )
            return False
        ok = await self.main_window.dialog(
            toga.ConfirmDialog(_("download_title"), _("download_message", model=model, size=format_gb(needed)))
        )
        if not ok:
            return False

        def on_progress(done: int, total: int) -> None:
            def apply() -> None:
                self.progress.value = done / total if total else 0
                self.status.text = _("downloading", done=format_gb(done), total=format_gb(total))

            self.loop.call_soon_threadsafe(apply)

        self.status.text = _("downloading", done=format_gb(0), total="…")
        try:
            await self.loop.run_in_executor(None, ensure_model, model, on_progress)
        except Exception as exc:  # noqa: BLE001 — network / disk errors
            await self.main_window.dialog(toga.ErrorDialog(_("download_failed"), str(exc)))
            return False
        self.progress.value = 0
        return True

    async def on_exit(self):
        if self.cancel_event is None:
            return True
        if await self.main_window.dialog(toga.ConfirmDialog(_("quit_title"), _("quit_message"))):
            self.cancel_event.set()
            return True
        return False


def main():
    return WhisperBatch()
