import json
import logging
from typing import Any

from api.conversation_service import append_message, get_history
from api.cube.client import CubeClientError, send_multimessage
from api.cube.models import CubeAcceptedMessage, CubeHandledMessage, CubeIncomingMessage, CubeQueuedMessage
from api.cube.payload import extract_cube_request_fields
from api.cube.queue import CubeQueueError, enqueue_incoming_message
from api.llm import LLMServiceError, generate_reply
from api.utils.logger import log_activity

logger = logging.getLogger(__name__)


class CubeWorkflowError(RuntimeError):
    status_code = 500


class CubePayloadError(CubeWorkflowError):
    status_code = 400


class CubeUpstreamError(CubeWorkflowError):
    status_code = 502


class CubeQueueUnavailableError(CubeWorkflowError):
    status_code = 503


def log_request(doc: dict[str, Any]) -> None:
    """Request logging stub for environments without persistent log store."""
    logger.info("request_log=%s", json.dumps(doc, ensure_ascii=False, default=str))


_WAKEUP_MESSAGE_ID = "-1"
_WAKEUP_PREFIX = "!@#"


def _is_wakeup_message(incoming: CubeIncomingMessage) -> bool:
    """Detect Cube wake-up signals that should not enter conversation history."""
    return incoming.message_id == _WAKEUP_MESSAGE_ID and incoming.message.startswith(_WAKEUP_PREFIX)


def accept_cube_message(payload: object) -> CubeAcceptedMessage:
    incoming = _parse_incoming_message(payload)

    if _is_wakeup_message(incoming):
        log_activity(
            "cube_wakeup_skipped",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
        )
        return CubeAcceptedMessage(
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            status="ignored",
        )

    try:
        was_queued = enqueue_incoming_message(incoming)
    except CubeQueueError as exc:
        log_activity(
            "cube_message_queue_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            error=str(exc),
        )
        raise CubeQueueUnavailableError("Cube message queue is unavailable.") from exc

    status = "accepted" if was_queued else "duplicate"
    log_request(
        {
            "user_id": incoming.user_id,
            "user_name": incoming.user_name,
            "channel_id": incoming.channel_id,
            "message_id": incoming.message_id,
            "user_message": incoming.message,
            "status": "queued" if was_queued else "duplicate",
            "processor": "queue",
        }
    )
    log_activity(
        "cube_message_queued" if was_queued else "cube_message_duplicate",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        processor="queue",
    )
    return CubeAcceptedMessage(
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        status=status,
    )


def handle_cube_message(payload: object) -> CubeHandledMessage:
    return process_incoming_message(_parse_incoming_message(payload))


def process_queued_message(queued_message: CubeQueuedMessage) -> CubeHandledMessage:
    return process_incoming_message(queued_message.incoming, attempt=queued_message.attempt)


def process_incoming_message(incoming: CubeIncomingMessage, *, attempt: int = 0) -> CubeHandledMessage:
    if _is_wakeup_message(incoming):
        log_activity(
            "cube_wakeup_skipped",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
        )
        return CubeHandledMessage(
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            user_message=incoming.message,
            llm_reply="",
        )

    log_activity(
        "cube_message_received",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        message_length=len(incoming.message),
        queue_attempt=attempt,
    )

    history = get_history(incoming.user_id)
    append_message(incoming.user_id, {"role": "user", "content": incoming.message})
    log_request(
        {
            "user_id": incoming.user_id,
            "user_name": incoming.user_name,
            "channel_id": incoming.channel_id,
            "message_id": incoming.message_id,
            "user_message": incoming.message,
            "history_length": len(history),
            "status": "received",
            "processor": "llm",
            "queue_attempt": attempt,
        }
    )
    log_activity(
        "cube_message_stored",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        processor="llm",
        conversation_length=len(history) + 1,
        queue_attempt=attempt,
    )

    try:
        llm_reply = generate_reply(history=history, user_message=incoming.message)
    except LLMServiceError as exc:
        log_activity(
            "cube_reply_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            reason="llm_error",
            error=str(exc),
            queue_attempt=attempt,
        )
        raise CubeUpstreamError("LLM reply generation failed.") from exc

    append_message(incoming.user_id, {"role": "assistant", "content": llm_reply})
    log_activity(
        "cube_llm_reply_generated",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        reply_length=len(llm_reply),
        queue_attempt=attempt,
    )

    try:
        send_multimessage(
            user_id=incoming.user_id,
            reply_message=llm_reply,
        )
    except CubeClientError as exc:
        log_activity(
            "cube_reply_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            reason="cube_delivery_error",
            error=str(exc),
            queue_attempt=attempt,
        )
        raise CubeUpstreamError("Cube multiMessage delivery failed.") from exc

    log_request(
        {
            "user_id": incoming.user_id,
            "user_name": incoming.user_name,
            "channel_id": incoming.channel_id,
            "message_id": incoming.message_id,
            "user_message": incoming.message,
            "assistant_message": llm_reply,
            "status": "replied",
            "processor": "llm",
            "queue_attempt": attempt,
        }
    )
    log_activity(
        "cube_reply_sent",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        reply_length=len(llm_reply),
        processor="llm",
        queue_attempt=attempt,
    )

    return CubeHandledMessage(
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        user_message=incoming.message,
        llm_reply=llm_reply,
    )


def _parse_incoming_message(payload: object) -> CubeIncomingMessage:
    if not isinstance(payload, dict):
        log_activity("cube_message_rejected", reason="invalid_payload")
        raise CubePayloadError("Invalid JSON payload")

    cube_fields = extract_cube_request_fields(payload)
    if cube_fields is None:
        log_activity("cube_message_rejected", reason="invalid_cube_payload")
        raise CubePayloadError("Invalid Cube payload")

    user_id = cube_fields["user_id"] or "unknown"
    user_name = cube_fields["user_name"] or ""
    message_id = cube_fields["message_id"] or ""
    channel_id = cube_fields["channel_id"] or ""
    raw_message = cube_fields["message"]

    if not isinstance(raw_message, str) or not raw_message.strip():
        log_activity(
            "cube_message_rejected",
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            message_id=message_id,
            reason="missing_message",
        )
        raise CubePayloadError("No message provided")

    return CubeIncomingMessage(
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        message_id=message_id,
        message=raw_message.strip(),
    )
