import logging
import sys
from logging import Handler
from logging.handlers import TimedRotatingFileHandler
from threading import Lock
from typing import TYPE_CHECKING, Any

from flask import g, has_request_context, request

from api import config
from api.utils.logger.formatters import (
    TEXT_LOG_FORMAT,
    JsonLineFormatter,
    LocalTimezoneFormatter,
    current_log_timestamp,
)
from api.utils.logger.paths import get_scoped_log_dir, get_theme_log_dir, normalize_name

if TYPE_CHECKING:
    from api.workflows.models import WorkflowState

_setup_lock = Lock()
_setup_done = False

_ROOT_HANDLER_TAG = "chatbot.root.stream"
_ACTIVITY_HANDLER_TAG = "chatbot.activity.json"
_TOPIC_HANDLER_TAG_PREFIX = "chatbot.topic."
_THEME_HANDLER_TAG_PREFIX = "chatbot.theme."
_WORKFLOW_HANDLER_TAG_PREFIX = "chatbot.workflow."


def _handler_tag(handler: Handler) -> str | None:
    return getattr(handler, "_chatbot_handler_tag", None)


def _set_handler_tag(handler: Handler, tag: str) -> None:
    handler._chatbot_handler_tag = tag


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
    retention_days: int,
    json_output: bool,
) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        file_path,
        when="midnight",
        interval=1,
        backupCount=max(1, retention_days),
        encoding="utf-8",
        utc=True,
    )
    if json_output:
        handler.setFormatter(JsonLineFormatter())
    else:
        handler.setFormatter(LocalTimezoneFormatter(TEXT_LOG_FORMAT))
    return handler


def setup_logging() -> None:
    """Configure stdout operational logs + themed JSON activity log files."""
    global _setup_done  # noqa: PLW0603
    if _setup_done:
        return
    with _setup_lock:
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        if not _has_handler(root, _ROOT_HANDLER_TAG):
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(LocalTimezoneFormatter(TEXT_LOG_FORMAT))
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
                retention_days=config.LOG_RETENTION_DAYS,
                json_output=True,
            )
            _set_handler_tag(file_handler, _ACTIVITY_HANDLER_TAG)
            activity_logger.addHandler(file_handler)

        _setup_done = True


def build_activity_payload(event: str, **data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "timestamp": current_log_timestamp(),
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


def log_workflow_activity(
    workflow_id: str,
    event: str,
    *,
    state: "WorkflowState | None" = None,
    level: int | str = logging.INFO,
    user_id: str | None = None,
    node_id: str | None = None,
    status: str | None = None,
    **data: Any,
) -> None:
    """Write a structured workflow-scoped event under ``logs/workflows/<workflow_id>/``."""
    try:
        setup_logging()
        if state is not None:
            user_id = user_id or getattr(state, "user_id", None)
            node_id = node_id or getattr(state, "node_id", None)
            status = status or getattr(state, "status", None)

        payload_data: dict[str, Any] = {
            "workflow_id": workflow_id,
            **data,
        }
        if user_id is not None:
            payload_data["user_id"] = user_id
        if node_id is not None:
            payload_data["node_id"] = node_id
        if status is not None:
            payload_data["status"] = status

        payload = build_activity_payload(event, **payload_data)
        get_workflow_logger(workflow_id).log(_parse_level(level), event, extra={"activity_data": payload})
    except Exception:
        logging.getLogger(__name__).exception(
            "Failed to write workflow activity log: workflow=%s event=%s",
            workflow_id,
            event,
        )


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
        retention_days=config.LOG_RETENTION_DAYS,
        json_output=json_output,
    )
    _set_handler_tag(file_handler, handler_tag)
    logger.addHandler(file_handler)
    return logger


def _get_scoped_logger(
    *,
    scope: str,
    scope_id: str,
    name: str,
    log_dir,
    handler_tag_prefix: str,
    json_output: bool,
    retention_days: int,
) -> logging.Logger:
    """Shared logic for theme/workflow scoped loggers."""
    safe_name = normalize_name(name, field_name="name")
    logger_name = f"{scope}.{scope_id}.{safe_name}"
    if json_output:
        logger_name += ".json"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler_tag = f"{handler_tag_prefix}{scope_id}.{safe_name}.{'json' if json_output else 'text'}"
    if _has_handler(logger, handler_tag):
        return logger

    suffix = "jsonl" if json_output else "log"
    file_handler = _build_file_handler(
        file_path=log_dir / f"{safe_name}.{suffix}",
        retention_days=retention_days,
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
    retention_days: int | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> logging.Logger:
    """Return a rotating logger saved under ``logs/<theme>/<name>.(log|jsonl)``."""
    setup_logging()
    _ = max_bytes
    safe_theme = normalize_name(theme, field_name="theme")
    return _get_scoped_logger(
        scope="theme",
        scope_id=safe_theme,
        name=name,
        log_dir=get_theme_log_dir(safe_theme),
        handler_tag_prefix=_THEME_HANDLER_TAG_PREFIX,
        json_output=json_output,
        retention_days=retention_days if retention_days is not None else (backup_count or config.LOG_RETENTION_DAYS),
    )


def get_workflow_logger(
    workflow_id: str,
    *,
    name: str = "events",
    json_output: bool = True,
    retention_days: int | None = None,
) -> logging.Logger:
    """Return a rotating logger saved under ``logs/workflows/<workflow_id>/<name>.(log|jsonl)``."""
    setup_logging()
    safe_workflow_id = normalize_name(workflow_id, field_name="workflow_id")
    return _get_scoped_logger(
        scope="workflow",
        scope_id=safe_workflow_id,
        name=name,
        log_dir=get_scoped_log_dir("workflows", safe_workflow_id),
        handler_tag_prefix=_WORKFLOW_HANDLER_TAG_PREFIX,
        json_output=json_output,
        retention_days=retention_days if retention_days is not None else config.LOG_RETENTION_DAYS,
    )


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
