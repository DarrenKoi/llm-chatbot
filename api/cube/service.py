import json
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from api import config
from api.conversation_service import ConversationStoreError, append_message
from api.cube import rich_blocks
from api.cube.chunker import plan_delivery
from api.cube.client import CubeClientError, send_multimessage, send_richnotification, send_richnotification_blocks
from api.cube.models import CubeAcceptedMessage, CubeHandledMessage, CubeIncomingMessage, CubeQueuedMessage
from api.cube.payload import extract_cube_request_fields
from api.cube.queue import CubeQueueError, enqueue_incoming_message
from api.logging_service import log_activity
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
    """요청 로그를 구조화된 JSON 형태로 Python 로거에 기록한다.

    영속적 로그 저장소가 없는 환경에서도 동작하는 최소 구현이다.
    """
    logger.info("request_log=%s", json.dumps(doc, ensure_ascii=False, default=str))


_WAKEUP_MESSAGE_ID = "-1"
_WAKEUP_PREFIX = "!@#"


def _is_wakeup_message(incoming: CubeIncomingMessage) -> bool:
    """Cube 플랫폼의 웨이크업 신호 여부를 판별한다.

    웨이크업 메시지는 대화 이력에 저장하지 않고 즉시 무시한다.
    """
    return incoming.message_id == _WAKEUP_MESSAGE_ID and incoming.message.startswith(_WAKEUP_PREFIX)


def accept_cube_message(payload: object) -> CubeAcceptedMessage:
    """Cube 웹훅 수신 직후 호출되는 빠른 수락 핸들러.

    메시지를 Redis 큐에 enqueue하고 즉시 accepted/duplicate/ignored 상태를 반환한다.
    실제 LLM 처리는 큐 워커(`cube/worker.py`)가 비동기로 담당한다.
    """
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
    """큐를 거치지 않고 Cube 메시지를 동기로 즉시 처리한다. 테스트나 직접 호출 용도로 사용한다."""
    return process_incoming_message(_parse_incoming_message(payload))


def process_queued_message(queued_message: CubeQueuedMessage) -> CubeHandledMessage:
    """큐에서 꺼낸 메시지를 처리한다. 재시도 횟수(attempt)를 함께 전달해 로그에 기록한다."""
    return process_incoming_message(queued_message.incoming, attempt=queued_message.attempt)


def _send_thinking_message(incoming: CubeIncomingMessage) -> None:
    """LLM 응답 대기 중임을 사용자에게 알리는 '생각 중...' 메시지를 Cube로 전송한다.

    LLM_THINKING_MESSAGE 환경 변수가 비어 있으면 전송하지 않는다.
    """
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
    """LangGraph 워크플로를 실행해 LLM 응답을 생성한다.

    LLM_THINKING_MESSAGE_DELAY_SECONDS가 설정된 경우, 지연 시간 내에 응답이 나오지 않으면
    먼저 '생각 중...' 메시지를 보내고 계속 대기한다.
    """
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
    """대화 이력 저장 시 함께 기록할 메타데이터 딕셔너리를 구성한다.

    direction은 'inbound'(사용자→봇) 또는 'outbound'(봇→사용자)이다.
    """
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


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_markdown_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(cell and set(cell) <= {":", "-", " "} and "-" in cell for cell in cells)


def _markdown_table_to_block(markdown_table: str) -> rich_blocks.Block | None:
    lines = [line for line in markdown_table.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    parsed_rows = [_split_markdown_table_row(line) for line in lines]
    separator_index = next(
        (index for index, cells in enumerate(parsed_rows) if index > 0 and _is_markdown_separator_row(cells)),
        -1,
    )
    if separator_index <= 0:
        return None

    headers = parsed_rows[separator_index - 1]
    rows = [row for index, row in enumerate(parsed_rows) if index > separator_index and row]
    return rich_blocks.add_table(headers, rows)


def _send_rich_delivery_item(*, user_id: str, channel_id: str, kind: str, content: str) -> None:
    if kind == "table":
        table_component = _markdown_table_to_block(content)
        if table_component is not None:
            send_richnotification_blocks(table_component, user_id=user_id, channel_id=channel_id)
            return

    send_richnotification(
        user_id=user_id,
        channel_id=channel_id,
        reply_message=content,
    )


def process_incoming_message(incoming: CubeIncomingMessage, *, attempt: int = 0) -> CubeHandledMessage:
    """CubeIncomingMessage를 받아 대화 저장 → LLM 호출 → Cube 전송의 전체 파이프라인을 실행한다.

    각 단계에서 실패하면 적절한 CubeWorkflowError를 발생시킨다.
    응답 전송 후 대화 저장에 실패해도 사용자 경험을 해치지 않도록 re-raise하지 않는다.
    """
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
        for item in plan_delivery(llm_reply):
            if item.method == "rich":
                _send_rich_delivery_item(
                    user_id=incoming.user_id,
                    channel_id=incoming.channel_id,
                    kind=item.kind,
                    content=item.content,
                )
            else:
                send_multimessage(
                    user_id=incoming.user_id,
                    reply_message=item.content,
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
    """raw Cube 페이로드(dict)를 파싱해 CubeIncomingMessage로 변환한다.

    필수 필드가 없거나 형식이 올바르지 않으면 CubePayloadError를 발생시킨다.
    require_message=False이면 빈 메시지도 허용한다(웨이크업 신호 처리용).
    """
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
