from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

TEXT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class JsonLineFormatter(logging.Formatter):
    """Format records as JSON lines for ingestion-friendly structured logs."""

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
