"""Minimal German/English UI strings, chosen from the macOS preferred language."""

from __future__ import annotations

import os

STRINGS: dict[str, dict[str, str]] = {
    "choose_folder": {"en": "Choose folder…", "de": "Ordner wählen…"},
    "no_folder": {"en": "No folder selected", "de": "Kein Ordner gewählt"},
    "language": {"en": "Language", "de": "Sprache"},
    "model": {"en": "Model", "de": "Modell"},
    "recursive": {"en": "Include subfolders", "de": "Unterordner einbeziehen"},
    "force": {"en": "Re-transcribe existing", "de": "Vorhandene neu transkribieren"},
    "start": {"en": "Start", "de": "Start"},
    "cancel": {"en": "Cancel", "de": "Abbrechen"},
    "cancelling": {"en": "Cancelling after current section…", "de": "Breche nach aktuellem Abschnitt ab…"},
    "show_in_finder": {"en": "Show in Finder", "de": "Im Finder zeigen"},
    "lang_auto": {"en": "Auto-detect", "de": "Automatisch erkennen"},
    "lang_de": {"en": "German", "de": "Deutsch"},
    "lang_en": {"en": "English", "de": "Englisch"},
    "lang_fr": {"en": "French", "de": "Französisch"},
    "lang_es": {"en": "Spanish", "de": "Spanisch"},
    "lang_it": {"en": "Italian", "de": "Italienisch"},
    "model_large": {"en": "Best quality (large-v3, ~3 GB)", "de": "Beste Qualität (large-v3, ~3 GB)"},
    "model_turbo": {"en": "Faster (large-v3-turbo, ~1.6 GB)", "de": "Schneller (large-v3-turbo, ~1,6 GB)"},
    "model_small": {"en": "Small (small, ~0.5 GB)", "de": "Klein (small, ~0,5 GB)"},
    "pending": {
        "en": "{pending} file(s) to transcribe, {skipped} already done",
        "de": "{pending} Datei(en) zu transkribieren, {skipped} bereits erledigt",
    },
    "nothing_to_do": {"en": "Nothing to transcribe in this folder.", "de": "In diesem Ordner gibt es nichts zu transkribieren."},
    "file_progress": {"en": "File {index} of {pending}: {name}", "de": "Datei {index} von {pending}: {name}"},
    "download_title": {"en": "Download model?", "de": "Modell herunterladen?"},
    "download_message": {
        "en": "The speech model is not on this Mac yet:\n\n{model}\n\nIt is downloaded once and then works offline. Download now?",
        "de": "Das Sprachmodell ist noch nicht auf diesem Mac:\n\n{model}\n\nEs wird einmalig geladen und funktioniert danach offline. Jetzt herunterladen?",
    },
    "downloading": {"en": "Downloading model… {done} of {total}", "de": "Lade Modell herunter… {done} von {total}"},
    "download_failed": {"en": "Download failed", "de": "Download fehlgeschlagen"},
    "done_title": {"en": "Finished", "de": "Fertig"},
    "done": {
        "en": "{processed} transcribed, {failed} failed, {skipped} skipped.",
        "de": "{processed} transkribiert, {failed} fehlgeschlagen, {skipped} übersprungen.",
    },
    "cancelled": {"en": "Cancelled. {processed} transcribed so far.", "de": "Abgebrochen. Bisher {processed} transkribiert."},
    "error_title": {"en": "Error", "de": "Fehler"},
    "quit_title": {"en": "Transcription running", "de": "Transkription läuft"},
    "quit_message": {
        "en": "Quit anyway? The current file will not be finished.",
        "de": "Trotzdem beenden? Die aktuelle Datei wird nicht fertig.",
    },
}


def _preferred_language() -> str:
    try:
        from rubicon.objc import ObjCClass

        langs = ObjCClass("NSLocale").preferredLanguages
        if langs.count:
            return str(langs.objectAtIndex(0))
    except Exception:  # noqa: BLE001 — fall back to environment
        pass
    return os.environ.get("LANG", "en")


LANG = os.environ.get("WHISPER_BATCH_UI_LANG") or ("de" if _preferred_language().lower().startswith("de") else "en")


def _(key: str, **kwargs: object) -> str:
    text = STRINGS[key].get(LANG) or STRINGS[key]["en"]
    return text.format(**kwargs) if kwargs else text
