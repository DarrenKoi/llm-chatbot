from pathlib import Path

from flask import current_app, has_app_context

from api import config


def normalize_name(value: str, *, field_name: str) -> str:
    normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    if not normalized:
        raise ValueError(f"{field_name} must contain at least one alphanumeric character")
    return normalized


def resolve_log_root_dir() -> Path:
    """Resolve root log directory with Flask app config override support."""
    if has_app_context():
        app_log_dir = current_app.config.get("LOG_DIR")
        if app_log_dir:
            resolved = Path(app_log_dir).expanduser()
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved

    root_dir = Path(config.LOG_DIR).expanduser()
    root_dir.mkdir(parents=True, exist_ok=True)
    return root_dir


def get_scoped_log_dir(*parts: str) -> Path:
    scoped_dir = resolve_log_root_dir()
    for index, part in enumerate(parts):
        safe_part = normalize_name(part, field_name=f"log_dir_part_{index}")
        scoped_dir = scoped_dir / safe_part

    scoped_dir.mkdir(parents=True, exist_ok=True)
    return scoped_dir


def get_theme_log_dir(theme: str) -> Path:
    return get_scoped_log_dir(theme)
