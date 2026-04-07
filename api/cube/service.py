import json
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from api import config
from api.conversation_service import ConversationStoreError, append_message
from api.cube.client import CubeClientError, send_multimessage
from api.cube.models import CubeAcceptedMessage, CubeHandledMessage, CubeIncomingMessage, CubeQueuedMessage
from api.cube.payload import extract_cube_request_fields
from api.cube.queue import CubeQueueError, enqueue_incoming_message
from api.utils.logger import log_activity
from api.workflows.lg_orchestrator import handle_message as handle_workflow_message
from api.workflows.models import WorkflowReply

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
    incoming = _parse_incoming_message(payload, require_message=False)

    if not incoming.message.strip():
        log_activity(
            "cube_empty_event_ignored",
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


def _send_thinking_message(incoming: CubeIncomingMessage) -> None:
    if not config.LLM_THINKING_MESSAGE:
        return

    try:
        send_multimessage(user_id=incoming.user_id, reply_message=config.LLM_THINKING_MESSAGE)
    except CubeClientError:
        log_activity(
            "cube_thinking_message_failed",
            level="WARNING",
            user_id=incoming.user_id,
            message_id=incoming.message_id,
        )


def _generate_llm_reply(incoming: CubeIncomingMessage, *, attempt: int = 0) -> WorkflowReply:
    if not config.LLM_THINKING_MESSAGE:
        return handle_workflow_message(incoming, attempt=attempt)

    delay_seconds = config.LLM_THINKING_MESSAGE_DELAY_SECONDS
    if delay_seconds <= 0:
        _send_thinking_message(incoming)
        return handle_workflow_message(incoming, attempt=attempt)

    with ThreadPoolExecutor(max_workers=1) as executor:
        logger.info(
            "Workflow handling scheduled: user_id=%s message_id=%s attempt=%d thinking_delay_seconds=%s",
            incoming.user_id,
            incoming.message_id,
            attempt,
            delay_seconds,
        )
        future = executor.submit(handle_workflow_message, incoming, attempt=attempt)
        try:
            return future.result(timeout=delay_seconds)
        except FutureTimeoutError:
            logger.info(
                "Workflow handling exceeded thinking delay: user_id=%s message_id=%s attempt=%d",
                incoming.user_id,
                incoming.message_id,
                attempt,
            )
            _send_thinking_message(incoming)
            return future.result()


def _build_conversation_metadata(
    incoming: CubeIncomingMessage,
    *,
    direction: str,
    reply_to_message_id: str | None = None,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "channel_id": incoming.channel_id,
        "source": "cube",
        "direction": direction,
        "user_name": incoming.user_name,
    }
    if direction == "inbound":
        metadata["message_id"] = incoming.message_id
    if reply_to_message_id:
        metadata["reply_to_message_id"] = reply_to_message_id
    if workflow_id:
        metadata["workflow_id"] = workflow_id
    return metadata


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

    try:
        append_message(
            incoming.user_id,
            {"role": "user", "content": incoming.message},
            conversation_id=incoming.channel_id,
            metadata=_build_conversation_metadata(incoming, direction="inbound"),
        )
    except ConversationStoreError as exc:
        log_activity(
            "cube_reply_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            reason="conversation_store_error",
            error=str(exc),
            queue_attempt=attempt,
        )
        raise CubeUpstreamError("Conversation storage is unavailable.") from exc
    log_request(
        {
            "user_id": incoming.user_id,
            "user_name": incoming.user_name,
            "channel_id": incoming.channel_id,
            "message_id": incoming.message_id,
            "user_message": incoming.message,
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
        queue_attempt=attempt,
    )

    try:
        workflow_result = _generate_llm_reply(incoming, attempt=attempt)
        llm_reply = workflow_result.reply
        workflow_id = workflow_result.workflow_id
    except Exception as exc:
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
        raise CubeUpstreamError("Workflow reply generation failed.") from exc

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

    try:
        append_message(
            incoming.user_id,
            {"role": "assistant", "content": llm_reply},
            conversation_id=incoming.channel_id,
            metadata=_build_conversation_metadata(
                incoming,
                direction="outbound",
                reply_to_message_id=incoming.message_id,
                workflow_id=workflow_id,
            ),
        )
    except ConversationStoreError:
        # 사용자에게 응답이 이미 전달된 상태이므로 re-raise하지 않는다.
        # 저장 실패는 로그로 추적하고, 대화 이력에만 누락이 발생한다.
        log_activity(
            "cube_conversation_store_append_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            reply_length=len(llm_reply),
            queue_attempt=attempt,
        )

    log_activity(
        "cube_llm_reply_generated",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        reply_length=len(llm_reply),
        queue_attempt=attempt,
    )

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


def _parse_incoming_message(payload: object, *, require_message: bool = True) -> CubeIncomingMessage:
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

    if not isinstance(raw_message, str):
        raw_message = ""

    if require_message and not raw_message.strip():
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
