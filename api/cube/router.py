import json
import logging

from flask import Blueprint, jsonify, request

from api.conversation_service import append_message
from api.cube.payload import extract_user_id
from api.utils.logger import log_activity

logger = logging.getLogger(__name__)

bp = Blueprint("cube", __name__)


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

    append_message(user_id, {"role": "user", "content": normalized_message})
    log_request(
        {
            "user_id": user_id,
            "user_name": user_name,
            "channel_id": channel_id,
            "message_id": message_id,
            "user_message": normalized_message,
            "status": "accepted",
            "processor": "external",
        }
    )
    log_activity(
        "cube_message_stored",
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        message_id=message_id,
        processor="external",
    )

    return jsonify({"status": "accepted", "message_id": message_id}), 202


def _extract_cube_request_fields(payload: dict) -> dict[str, str | None] | None:
    user_id = extract_user_id(payload) or "unknown"

    rich_message = payload.get("richnotificationmessage")
    if isinstance(rich_message, dict):
        header = rich_message.get("header")
        process = rich_message.get("process")
        sender = header.get("from") if isinstance(header, dict) else None
        if not isinstance(sender, dict) or not isinstance(process, dict):
            return None
        return {
            "user_id": user_id,
            "message_id": str(sender.get("messageid") or ""),
            "channel_id": str(sender.get("channelid") or ""),
            "user_name": str(sender.get("username") or ""),
            "message": process.get("processdata"),
        }

    return {
        "user_id": user_id,
        "message_id": str(payload.get("message_id") or ""),
        "channel_id": str(payload.get("channel") or ""),
        "user_name": str(payload.get("user_name") or ""),
        "message": payload.get("message"),
    }
