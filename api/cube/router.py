import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, request

from api import config
from api.conversation_service import append_message, append_messages, get_history
from api.llm import chat
from api.utils.logger import log_activity

logger = logging.getLogger(__name__)

bp = Blueprint("cube", __name__)
executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)


def send_rich_notification(channel_id: str, text: str, image_url: str | None = None) -> None:
    """Temporary local stub for Cube notification sending."""
    logger.info("[CUBE STUB] channel=%s text=%s image=%s", channel_id, text[:100], image_url)


def log_request(doc: dict) -> None:
    """Request logging stub for environments without persistent log store."""
    logger.info("request_log=%s", json.dumps(doc, ensure_ascii=False, default=str))


@bp.route("/api/v1/cube/receiver", methods=["POST"])
def receive_cube():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        log_activity("cube_message_rejected", reason="invalid_payload")
        return jsonify({"error": "Invalid JSON payload"}), 400

    cube_fields = _extract_cube_request_fields(payload)
    if cube_fields is None:
        log_activity("cube_message_rejected", reason="invalid_cube_payload")
        return jsonify({"error": "Invalid Cube payload"}), 400

    user_id = cube_fields["user_id"]
    user_name = cube_fields["user_name"]
    message_id = cube_fields["message_id"]
    channel_id = cube_fields["channel_id"]
    user_message = cube_fields["message"]

    if not isinstance(user_message, str) or not user_message.strip():
        log_activity(
            "cube_message_rejected",
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            message_id=message_id,
            reason="missing_message",
        )
        return jsonify({"error": "No message provided"}), 400

    normalized_message = user_message.strip()
    log_activity(
        "cube_message_received",
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        message_id=message_id,
        message_length=len(normalized_message),
    )

    history = get_history(user_id)
    user_msg = {"role": "user", "content": normalized_message}
    append_message(user_id, user_msg)

    executor.submit(_process_llm_request, user_id, user_name, channel_id, message_id, history, user_msg)

    return jsonify({"status": "accepted", "message_id": message_id}), 202


def _process_llm_request(
    user_id: str,
    user_name: str,
    channel_id: str,
    message_id: str,
    history: list[dict],
    user_msg: dict,
) -> None:
    """Background worker: call LLM and send reply via Cube."""
    start = time.monotonic()
    log_activity(
        "llm_job_started",
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        message_id=message_id,
        history_size=len(history),
    )

    try:
        messages = [{"role": "system", "content": config.LLM_SYSTEM_PROMPT}] + history + [user_msg]
        reply_text, new_messages, metadata = chat(messages)
        append_messages(user_id, new_messages)

        image_url = _extract_image_url(new_messages)
        if channel_id:
            send_rich_notification(channel_id, reply_text, image_url=image_url)

        total_duration_ms = int((time.monotonic() - start) * 1000)
        log_activity(
            "llm_job_succeeded",
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            message_id=message_id,
            duration_ms=total_duration_ms,
            llm_call_count=len(metadata["llm_calls"]),
            tool_execution_count=len(metadata["tool_executions"]),
            image_generated=bool(image_url),
        )

        log_request(
            {
                "user_id": user_id,
                "user_name": user_name,
                "channel_id": channel_id,
                "message_id": message_id,
                "user_message": user_msg["content"],
                "reply_text": reply_text,
                "model": config.LLM_MODEL,
                "status": "success",
                "error": None,
                "total_duration_ms": total_duration_ms,
                "llm_calls": metadata["llm_calls"],
                "tool_executions": metadata["tool_executions"],
            }
        )
    except Exception as exc:
        logger.exception("Error processing LLM request for user %s", user_id)
        total_duration_ms = int((time.monotonic() - start) * 1000)
        log_activity(
            "llm_job_failed",
            level="ERROR",
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            message_id=message_id,
            duration_ms=total_duration_ms,
            error=str(exc),
        )

        if channel_id:
            send_rich_notification(channel_id, "Sorry, something went wrong. Please try again.")

        log_request(
            {
                "user_id": user_id,
                "user_name": user_name,
                "channel_id": channel_id,
                "message_id": message_id,
                "user_message": user_msg["content"],
                "reply_text": None,
                "model": config.LLM_MODEL,
                "status": "error",
                "error": str(exc),
                "total_duration_ms": total_duration_ms,
                "llm_calls": [],
                "tool_executions": [],
            }
        )


def _extract_image_url(messages: list[dict]) -> str | None:
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        try:
            content = json.loads(msg["content"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(content, dict) and "image_url" in content:
            return content["image_url"]
    return None


def _extract_cube_request_fields(payload: dict) -> dict[str, str | None] | None:
    rich_message = payload.get("richnotificationmessage")
    if isinstance(rich_message, dict):
        header = rich_message.get("header")
        process = rich_message.get("process")
        sender = header.get("from") if isinstance(header, dict) else None
        if not isinstance(sender, dict) or not isinstance(process, dict):
            return None
        return {
            "user_id": str(sender.get("uniquename") or "unknown"),
            "message_id": str(sender.get("messageid") or ""),
            "channel_id": str(sender.get("channelid") or ""),
            "user_name": str(sender.get("username") or ""),
            "message": process.get("processdata"),
        }

    return {
        "user_id": str(payload.get("user") or payload.get("user_id") or "unknown"),
        "message_id": str(payload.get("message_id") or ""),
        "channel_id": str(payload.get("channel") or ""),
        "user_name": str(payload.get("user_name") or ""),
        "message": payload.get("message"),
    }
