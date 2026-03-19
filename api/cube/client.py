from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from api import config
from api.cube.payload import build_multimessage_payload, build_richnotification_payload


class CubeClientError(RuntimeError):
    """Raised when message delivery to Cube fails."""


def _send_cube_request(*, url: str, payload: dict[str, Any], label: str) -> dict[str, Any] | None:
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=config.CUBE_TIMEOUT_SECONDS) as response:
            raw_body = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CubeClientError(f"Cube {label} failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise CubeClientError(f"Cube {label} failed: {exc.reason}") from exc

    if not raw_body:
        return None

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"raw": raw_body.decode("utf-8", errors="replace")}

    if not isinstance(data, dict):
        return {"payload": data}
    return data


def send_multimessage(*, user_id: str, reply_message: str) -> dict[str, Any] | None:
    if not config.CUBE_MULTIMESSAGE_URL:
        raise CubeClientError("CUBE_MULTIMESSAGE_URL is not configured.")
    if not config.CUBE_API_ID:
        raise CubeClientError("CUBE_API_ID is not configured.")
    if not config.CUBE_API_TOKEN:
        raise CubeClientError("CUBE_API_TOKEN is not configured.")

    payload = build_multimessage_payload(user_id=user_id, reply_message=reply_message)
    return _send_cube_request(url=config.CUBE_MULTIMESSAGE_URL, payload=payload, label="multiMessage")


def send_richnotification(*, user_id: str, channel_id: str, reply_message: str) -> dict[str, Any] | None:
    if not config.CUBE_RICHNOTIFICATION_URL:
        raise CubeClientError("CUBE_RICHNOTIFICATION_URL is not configured.")
    if not config.CUBE_BOT_ID:
        raise CubeClientError("CUBE_BOT_ID is not configured.")
    if not config.CUBE_BOT_TOKEN:
        raise CubeClientError("CUBE_BOT_TOKEN is not configured.")

    payload = build_richnotification_payload(
        user_id=user_id,
        channel_id=channel_id,
        reply_message=reply_message,
    )
    return _send_cube_request(url=config.CUBE_RICHNOTIFICATION_URL, payload=payload, label="richnotification")
