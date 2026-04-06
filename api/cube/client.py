import json
import logging
from typing import Any

import httpx

from api import config
from api.cube.payload import build_multimessage_payload, build_richnotification_payload

logger = logging.getLogger(__name__)


class CubeClientError(RuntimeError):
    """Raised when message delivery to Cube fails."""


def _send_cube_request(*, url: str, payload: dict[str, Any], label: str) -> dict[str, Any] | None:
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=config.CUBE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CubeClientError(f"Cube {label} failed with HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise CubeClientError(f"Cube {label} failed: {exc}") from exc

    raw_body = response.content

    if not raw_body:
        return None

    try:
        data = response.json()
    except json.JSONDecodeError:
        return {"raw": response.text}

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
    logger.info(
        "Cube multiMessage send started: user_id=%s reply_length=%d",
        user_id,
        len(reply_message),
    )
    result = _send_cube_request(url=config.CUBE_MULTIMESSAGE_URL, payload=payload, label="multiMessage")
    logger.info(
        "Cube multiMessage send completed: user_id=%s reply_length=%d response_type=%s",
        user_id,
        len(reply_message),
        type(result).__name__,
    )
    return result


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
    logger.info(
        "Cube richnotification send started: user_id=%s channel_id=%s reply_length=%d",
        user_id,
        channel_id,
        len(reply_message),
    )
    result = _send_cube_request(url=config.CUBE_RICHNOTIFICATION_URL, payload=payload, label="richnotification")
    logger.info(
        "Cube richnotification send completed: user_id=%s channel_id=%s reply_length=%d response_type=%s",
        user_id,
        channel_id,
        len(reply_message),
        type(result).__name__,
    )
    return result
