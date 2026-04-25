"""웹 채팅 API의 Flask Blueprint."""

import logging
from dataclasses import asdict

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException, Unauthorized

from api.conversation_service import ConversationStoreError
from api.logging_service import log_activity
from api.web_chat.identity import get_current_web_chat_user
from api.web_chat.service import (
    get_conversation_messages,
    list_user_conversations,
    send_web_chat_message,
)

logger = logging.getLogger(__name__)

bp = Blueprint("web_chat", __name__, url_prefix="/api/v1/web-chat")


@bp.errorhandler(Unauthorized)
def _handle_unauthorized(error: Unauthorized):
    return _error_response(401, "unauthorized", error.description)


@bp.errorhandler(BadRequest)
def _handle_bad_request(error: BadRequest):
    return _error_response(400, "bad_request", error.description)


@bp.route("/me", methods=["GET"])
def me():
    user = get_current_web_chat_user()
    return jsonify(asdict(user))


@bp.route("/conversations", methods=["GET"])
def conversations():
    user = get_current_web_chat_user()
    limit = _resolve_limit(default=20, maximum=100)
    summaries = list_user_conversations(user, limit=limit)
    return jsonify({"conversations": [asdict(summary) for summary in summaries]})


@bp.route("/conversations/<conversation_id>/messages", methods=["GET"])
def list_messages(conversation_id: str):
    user = get_current_web_chat_user()
    limit = _resolve_limit(default=50, maximum=200)
    messages = get_conversation_messages(user, conversation_id, limit=limit)
    return jsonify({"conversation_id": conversation_id, "messages": messages})


@bp.route("/conversations/<conversation_id>/messages", methods=["POST"])
def post_message(conversation_id: str):
    user = get_current_web_chat_user()
    payload = _resolve_json_payload()
    text = str(payload.get("message", ""))
    try:
        reply = send_web_chat_message(user, conversation_id, text)
    except ConversationStoreError:
        return _error_response(503, "conversation_store_unavailable", "Conversation storage is unavailable.")
    except HTTPException:
        raise
    except Exception:
        logger.exception("web_chat send failed")
        log_activity(
            "web_chat_send_failed",
            level="ERROR",
            user_id=user.user_id,
            conversation_id=conversation_id,
        )
        return _error_response(502, "workflow_failed", "Failed to generate a reply.")
    return jsonify(asdict(reply))


def _resolve_json_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise BadRequest("Request body must be a JSON object.")
    return payload


def _resolve_limit(*, default: int, maximum: int) -> int:
    raw = request.args.get("limit")
    if raw is None:
        return default
    try:
        return max(1, min(int(raw), maximum))
    except ValueError:
        return default


def _error_response(status: int, error: str, detail: str | None = None):
    body = {"error": error}
    if detail:
        body["detail"] = detail
    return jsonify(body), status
