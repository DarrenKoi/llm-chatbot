import json
import logging
from typing import Any

import httpx

from api import config
from api.cube import rich_blocks
from api.cube.payload import build_multimessage_payload, build_richnotification_payload

logger = logging.getLogger(__name__)


class CubeClientError(RuntimeError):
    """Raised when message delivery to Cube fails."""


def _send_cube_request(*, url: str, payload: dict[str, Any], label: str) -> dict[str, Any] | None:
    logger.info("Cube %s request started", label)
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
        logger.info("Cube %s request completed: empty_response=True", label)
        return None

    try:
        data = response.json()
    except json.JSONDecodeError:
        logger.info("Cube %s request completed: raw_text=True", label)
        return {"raw": response.text}

    if not isinstance(data, dict):
        logger.info("Cube %s request completed: wrapped=True", label)
        return {"payload": data}
    logger.info("Cube %s request completed", label)
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


def send_richnotification_blocks(
    *blocks: rich_blocks.Block,
    user_id: str,
    channel_id: str,
    callback_address: str | None = None,
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
) -> dict[str, Any] | None:
    if not config.CUBE_RICHNOTIFICATION_URL:
        raise CubeClientError("CUBE_RICHNOTIFICATION_URL is not configured.")
    if not config.CUBE_BOT_ID:
        raise CubeClientError("CUBE_BOT_ID is not configured.")
    if not config.CUBE_BOT_TOKEN:
        raise CubeClientError("CUBE_BOT_TOKEN is not configured.")

    resolved_callback_address = callback_address
    if resolved_callback_address is None:
        resolved_callback_address = (
            config.CUBE_RICHNOTIFICATION_CALLBACK_URL if any(block.requestid for block in blocks) else ""
        )

    content_item = rich_blocks.add_container(
        *blocks,
        callback_address=resolved_callback_address,
        session_id=session_id,
        sequence=sequence,
        summary=summary,
    )
    payload = build_richnotification_payload(
        user_id=user_id,
        channel_id=channel_id,
        content_items=[content_item],
    )
    return _send_cube_request(url=config.CUBE_RICHNOTIFICATION_URL, payload=payload, label="richnotification")
