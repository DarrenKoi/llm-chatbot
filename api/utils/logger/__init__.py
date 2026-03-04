from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any

from flask import g, has_request_context, request

from api import config

TEXT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_setup_lock = Lock()

_ROOT_HANDLER_TAG = "chatbot.root.stream"
_ACTIVITY_HANDLER_TAG = "chatbot.activity.json"
_TOPIC_HANDLER_TAG_PREFIX = "chatbot.topic."


class JsonLineFormatter(logging.Formatter):
    """Format log records as JSON lines for OpenSearch/MongoDB-friendly ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "activity_data", None)
        if not isinstance(payload, dict):
            payload = {"event": record.getMessage()}
        else:
            payload = dict(payload)

        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        payload.setdefault("level", record.levelname)
        payload.setdefault("logger", record.name)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _handler_tag(handler: Handler) -> str | None:
    return getattr(handler, "_chatbot_handler_tag", None)


def _set_handler_tag(handler: Handler, tag: str) -> None:
    setattr(handler, "_chatbot_handler_tag", tag)


def _has_handler(logger: logging.Logger, tag: str) -> bool:
    return any(_handler_tag(handler) == tag for handler in logger.handlers)


def _activity_log_dir() -> Path:
    log_dir = Path(config.ACTIVITY_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _normalize_topic(topic: str) -> str:
    normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in topic.strip())
    if not normalized:
        raise ValueError("topic must contain at least one alphanumeric character")
    return normalized


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


def setup_logging() -> None:
    """Configure stdout operational logs + JSON activity logs with rollover."""
    with _setup_lock:
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        if not _has_handler(root, _ROOT_HANDLER_TAG):
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT))
            _set_handler_tag(stream_handler, _ROOT_HANDLER_TAG)
            root.addHandler(stream_handler)

        activity_logger = logging.getLogger("activity")
        activity_logger.setLevel(logging.INFO)
        activity_logger.propagate = False

        if not _has_handler(activity_logger, _ACTIVITY_HANDLER_TAG):
            file_handler = RotatingFileHandler(
                _activity_log_dir() / "activity.jsonl",
                maxBytes=config.ACTIVITY_LOG_MAX_BYTES,
                backupCount=config.ACTIVITY_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(JsonLineFormatter())
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
    """Return a rotating logger for a topic under ``api/utils/logger/logs``."""
    setup_logging()
    safe_topic = _normalize_topic(topic)
    logger_name = f"topic.{safe_topic}.json" if json_output else f"topic.{safe_topic}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler_tag = f"{_TOPIC_HANDLER_TAG_PREFIX}{safe_topic}.{'json' if json_output else 'text'}"
    if _has_handler(logger, handler_tag):
        return logger

    suffix = "jsonl" if json_output else "log"
    file_handler = RotatingFileHandler(
        _activity_log_dir() / f"{safe_topic}.{suffix}",
        maxBytes=config.TOPIC_LOG_MAX_BYTES,
        backupCount=config.TOPIC_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    if json_output:
        file_handler.setFormatter(JsonLineFormatter())
    else:
        file_handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT))

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


__all__ = [
    "build_activity_payload",
    "get_topic_logger",
    "log_activity",
    "rollover_activity_logs",
    "rollover_logs",
    "rollover_topic_logs",
    "setup_logging",
]
