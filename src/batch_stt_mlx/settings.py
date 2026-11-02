"""TOML settings + CLI overrides."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

DEFAULT_AUDIO_EXTENSIONS: tuple[str, ...] = (
    "wav",
    "mp3",
    "m4a",
    "aac",
    "flac",
    "ogg",
    "opus",
    "wma",
    "aiff",
    "aif",
    "caf",
    "amr",
    "3gp",
    "3ga",
    "mp4",
    "m4v",
    "mov",
    "mkv",
    "webm",
    "avi",
)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-mlx"


@dataclass
class Settings:
    model: str = DEFAULT_MODEL
    language: str | None = None
    recursive: bool = False
    force: bool = False
    dry_run: bool = False
    verbose: bool = False
    log_name: str = "batch-stt.log"
    monitor_chunk_secs: float = 90.0
    loop_max_consecutive: int = 5
    loop_mode_fraction: float = 0.4
    loop_mode_min_segments: int = 12
    max_attempts: int = 2
    condition_on_previous_text_first: bool = True
    condition_on_previous_text_retry: bool = False
    initial_prompt_chars: int = 224
    audio_extensions: tuple[str, ...] = DEFAULT_AUDIO_EXTENSIONS
    config_path: Path | None = None
    directory: Path = field(default_factory=lambda: Path("."))


def _config_search_paths(explicit: Path | None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    return [
        Path.cwd() / "batch-stt.toml",
        Path.home() / ".rphki" / "batch-stt.toml",
    ]


def find_config_file(explicit: Path | None = None) -> Path | None:
    for path in _config_search_paths(explicit):
        if path.is_file():
            return path
    return None


def _normalize_language(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "auto"}:
        return None
    return text


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a table: {path}")
    return data


def settings_from_toml(data: dict[str, Any], *, config_path: Path | None = None) -> Settings:
    kwargs: dict[str, Any] = {"config_path": config_path}
    mapping = {
        "model": "model",
        "recursive": "recursive",
        "force": "force",
        "verbose": "verbose",
        "log_name": "log_name",
        "monitor_chunk_secs": "monitor_chunk_secs",
        "loop_max_consecutive": "loop_max_consecutive",
        "loop_mode_fraction": "loop_mode_fraction",
        "loop_mode_min_segments": "loop_mode_min_segments",
        "max_attempts": "max_attempts",
        "condition_on_previous_text_first": "condition_on_previous_text_first",
        "condition_on_previous_text_retry": "condition_on_previous_text_retry",
        "initial_prompt_chars": "initial_prompt_chars",
    }
    for key, attr in mapping.items():
        if key in data:
            kwargs[attr] = data[key]
    if "language" in data:
        kwargs["language"] = _normalize_language(data["language"])
    if "audio_extensions" in data:
        exts = data["audio_extensions"]
        if not isinstance(exts, list) or not all(isinstance(x, str) for x in exts):
            raise ValueError("audio_extensions must be a list of strings")
        kwargs["audio_extensions"] = tuple(e.lower().lstrip(".") for e in exts)
    return Settings(**kwargs)


def load_settings(
    *,
    config: Path | None = None,
    directory: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    path = find_config_file(config)
    settings = settings_from_toml(_load_toml(path), config_path=path) if path else Settings()
    if directory is not None:
        settings = replace(settings, directory=directory)
    if overrides:
        cleaned = {k: v for k, v in overrides.items() if v is not None}
        if "language" in cleaned:
            cleaned["language"] = _normalize_language(cleaned["language"])
        settings = replace(settings, **cleaned)
    return settings


def merge_cli_overrides(
    settings: Settings,
    *,
    model: str | None = None,
    language: str | None = None,
    recursive: bool | None = None,
    force: bool | None = None,
    dry_run: bool | None = None,
    verbose: bool | None = None,
) -> Settings:
    overrides: dict[str, Any] = {}
    if model is not None:
        overrides["model"] = model
    if language is not None:
        overrides["language"] = language
    if recursive is not None:
        overrides["recursive"] = recursive
    if force is not None:
        overrides["force"] = force
    if dry_run is not None:
        overrides["dry_run"] = dry_run
    if verbose is not None:
        overrides["verbose"] = verbose
    return replace(settings, **overrides) if overrides else settings
