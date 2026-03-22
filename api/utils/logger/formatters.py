import json
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api import config

TEXT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_LOG_TIMEZONE = "Asia/Seoul"


class JsonLineFormatter(logging.Formatter):
    """Format records as JSON lines for ingestion-friendly structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "activity_data", None)
        if not isinstance(payload, dict):
            payload = {"event": record.getMessage()}
        document = build_log_document(record, payload)

        if record.exc_info:
            document["exception"] = self.formatException(record.exc_info)

        return json.dumps(document, ensure_ascii=False, default=str)


class LocalTimezoneFormatter(logging.Formatter):
    """Format text logs using the configured application timezone."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=get_log_timezone())
        if datefmt:
            return timestamp.strftime(datefmt)
        return timestamp.strftime(self.default_time_format)


def get_log_timezone() -> ZoneInfo:
    configured_timezone = getattr(config, "LOG_TIMEZONE", _DEFAULT_LOG_TIMEZONE) or _DEFAULT_LOG_TIMEZONE
    try:
        return ZoneInfo(configured_timezone)
    except ZoneInfoNotFoundError:
        try:
            return ZoneInfo(_DEFAULT_LOG_TIMEZONE)
        except ZoneInfoNotFoundError:
            return timezone.utc


def _normalize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=get_log_timezone())
    else:
        value = value.astimezone(get_log_timezone())
    return value.isoformat()


def current_log_timestamp() -> str:
    return datetime.now(get_log_timezone()).isoformat()


def _sanitize_key(key: str) -> str:
    safe_key = key.replace("\x00", "").replace(".", "_")
    if safe_key.startswith("$"):
        safe_key = f"_{safe_key.lstrip('$')}"
    return safe_key or "field"


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return _normalize_datetime(value)

    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            safe_key = _sanitize_key(str(raw_key))
            candidate_key = safe_key
            duplicate_idx = 1
            while candidate_key in normalized:
                duplicate_idx += 1
                candidate_key = f"{safe_key}_{duplicate_idx}"
            normalized[candidate_key] = _normalize_for_json(raw_value)
        return normalized

    if isinstance(value, (list, tuple, set)):
        return [_normalize_for_json(item) for item in value]

    return value


def build_log_document(record: logging.LogRecord, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = _normalize_for_json(payload)
    if not isinstance(normalized_payload, dict):
        normalized_payload = {"payload": normalized_payload}

    message = str(normalized_payload.get("message", record.getMessage()))
    event = str(normalized_payload.get("event", message))
    timestamp = str(normalized_payload.get("@timestamp") or normalized_payload.get("timestamp")
                    or current_log_timestamp())

    document: dict[str, Any] = {
        "timestamp": timestamp,
        "event": event,
        "message": message,
        "level": record.levelname,
        "logger": record.name,
        "service": config.APP_NAME,
    }

    for key, value in normalized_payload.items():
        if key in {"@timestamp", "timestamp"}:
            continue
        if key in {"event", "message"}:
            continue
        if key in document:
            document[f"data_{key}"] = value
            continue
        document[key] = value

    return document
