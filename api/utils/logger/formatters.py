from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from api import config

TEXT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


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


def _sanitize_key(key: str) -> str:
    safe_key = key.replace("\x00", "").replace(".", "_")
    if safe_key.startswith("$"):
        safe_key = f"_{safe_key.lstrip('$')}"
    return safe_key or "field"


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()

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
                    or datetime.now(timezone.utc).isoformat())

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
