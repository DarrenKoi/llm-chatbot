from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from logging import Handler
from logging.handlers import RotatingFileHandler
from threading import Lock
from typing import Any

from flask import g, has_request_context, request

from api import config
from api.utils.logger.formatters import JsonLineFormatter, TEXT_LOG_FORMAT
from api.utils.logger.paths import get_theme_log_dir, normalize_name

_setup_lock = Lock()

_ROOT_HANDLER_TAG = "chatbot.root.stream"
_ACTIVITY_HANDLER_TAG = "chatbot.activity.json"
_TOPIC_HANDLER_TAG_PREFIX = "chatbot.topic."
_THEME_HANDLER_TAG_PREFIX = "chatbot.theme."


def _handler_tag(handler: Handler) -> str | None:
    return getattr(handler, "_chatbot_handler_tag", None)


def _set_handler_tag(handler: Handler, tag: str) -> None:
    setattr(handler, "_chatbot_handler_tag", tag)


def _has_handler(logger: logging.Logger, tag: str) -> bool:
    return any(_handler_tag(handler) == tag for handler in logger.handlers)


def _parse_level(level: int | str) -> int:
    if isinstance(level, int):
        return level

    mapped_level = logging.getLevelName(level.upper())
    if isinstance(mapped_level, int):
        return mapped_level
    raise ValueError(f"Invalid log level: {level}")


def _request_context() -> dict[str, Any]:
    if not has_request_context():
        return {}

    context: dict[str, Any] = {
        "request_id": getattr(g, "request_id", None),
        "method": request.method,
        "path": request.path,
    }
    return {key: value for key, value in context.items() if value is not None}


def _build_file_handler(
    *,
    file_path,
    max_bytes: int,
    backup_count: int,
    json_output: bool,
) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    if json_output:
        handler.setFormatter(JsonLineFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT))
    return handler


def setup_logging() -> None:
    """Configure stdout operational logs + themed JSON activity log files."""
    with _setup_lock:
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        if not _has_handler(root, _ROOT_HANDLER_TAG):
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT))
            _set_handler_tag(stream_handler, _ROOT_HANDLER_TAG)
            root.addHandler(stream_handler)

        activity_theme = normalize_name(config.ACTIVITY_LOG_THEME, field_name="ACTIVITY_LOG_THEME")
        activity_logger = logging.getLogger("activity")
        activity_logger.setLevel(logging.INFO)
        activity_logger.propagate = False

        if not _has_handler(activity_logger, _ACTIVITY_HANDLER_TAG):
            activity_dir = get_theme_log_dir(activity_theme)
            file_handler = _build_file_handler(
                file_path=activity_dir / "activity.jsonl",
                max_bytes=config.ACTIVITY_LOG_MAX_BYTES,
                backup_count=config.ACTIVITY_LOG_BACKUP_COUNT,
                json_output=True,
            )
            _set_handler_tag(file_handler, _ACTIVITY_HANDLER_TAG)
            activity_logger.addHandler(file_handler)


def build_activity_payload(event: str, **data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(_request_context())
    payload.update(data)
    return payload


def log_activity(event: str, *, level: int | str = logging.INFO, **data: Any) -> None:
    """Write structured activity records for user/server events."""
    try:
        setup_logging()
        payload = build_activity_payload(event, **data)
        logging.getLogger("activity").log(_parse_level(level), event, extra={"activity_data": payload})
    except Exception:
        logging.getLogger(__name__).exception("Failed to write structured activity log")


def get_topic_logger(topic: str, *, json_output: bool = False) -> logging.Logger:
    """Return a rotating logger saved under ``logs/<topic>/``."""
    setup_logging()
    safe_topic = normalize_name(topic, field_name="topic")
    logger_name = f"topic.{safe_topic}.json" if json_output else f"topic.{safe_topic}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler_tag = f"{_TOPIC_HANDLER_TAG_PREFIX}{safe_topic}.{'json' if json_output else 'text'}"
    if _has_handler(logger, handler_tag):
        return logger

    suffix = "jsonl" if json_output else "log"
    topic_dir = get_theme_log_dir(safe_topic)
    file_handler = _build_file_handler(
        file_path=topic_dir / f"{safe_topic}.{suffix}",
        max_bytes=config.TOPIC_LOG_MAX_BYTES,
        backup_count=config.TOPIC_LOG_BACKUP_COUNT,
        json_output=json_output,
    )
    _set_handler_tag(file_handler, handler_tag)
    logger.addHandler(file_handler)
    return logger


def get_theme_logger(
    theme: str,
    *,
    name: str = "events",
    json_output: bool = False,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> logging.Logger:
    """Return a rotating logger saved under ``logs/<theme>/<name>.(log|jsonl)``."""
    setup_logging()
    safe_theme = normalize_name(theme, field_name="theme")
    safe_name = normalize_name(name, field_name="name")
    logger_name = f"theme.{safe_theme}.{safe_name}.json" if json_output else f"theme.{safe_theme}.{safe_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler_tag = f"{_THEME_HANDLER_TAG_PREFIX}{safe_theme}.{safe_name}.{'json' if json_output else 'text'}"
    if _has_handler(logger, handler_tag):
        return logger

    suffix = "jsonl" if json_output else "log"
    themed_dir = get_theme_log_dir(safe_theme)
    file_handler = _build_file_handler(
        file_path=themed_dir / f"{safe_name}.{suffix}",
        max_bytes=max_bytes or config.TOPIC_LOG_MAX_BYTES,
        backup_count=backup_count if backup_count is not None else config.TOPIC_LOG_BACKUP_COUNT,
        json_output=json_output,
    )
    _set_handler_tag(file_handler, handler_tag)
    logger.addHandler(file_handler)
    return logger


def _rollover_logger_handlers(logger: logging.Logger) -> int:
    rolled = 0
    for handler in logger.handlers:
        if hasattr(handler, "doRollover"):
            handler.doRollover()
            rolled += 1
    return rolled


def rollover_activity_logs() -> int:
    """Force rollover for the structured activity log handlers."""
    setup_logging()
    return _rollover_logger_handlers(logging.getLogger("activity"))


def rollover_topic_logs() -> int:
    """Force rollover for all configured topic loggers."""
    setup_logging()
    total = 0
    manager = logging.root.manager
    for name, logger_obj in manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger) and name.startswith("topic."):
            total += _rollover_logger_handlers(logger_obj)
    return total


def rollover_logs() -> int:
    """Force rollover for activity + topic loggers and return rolled handler count."""
    return rollover_activity_logs() + rollover_topic_logs()
