"""웹 채널 메시지 처리 서비스.

cube/service.py의 흐름 중 마지막 Cube 송신 단계만 빼고 동일하게:
저장 → LangGraph 워크플로 → 저장. LangGraph thread는 (user_id, conversation_id)로 식별되므로
같은 conversation_id를 다시 사용하면 같은 thread가 이어진다.
"""

import logging
import uuid
from typing import Any

from werkzeug.exceptions import BadRequest

from api.conversation_service import (
    ConversationStoreError,
    ConversationSummary,
    append_message,
    get_history,
    list_conversations,
)
from api.cube.models import CubeIncomingMessage
from api.logging_service import log_activity
from api.web_chat.models import (
    WebChatConversationSummary,
    WebChatReply,
    WebChatUser,
)
from api.workflows.lg_orchestrator import handle_message
from api.workflows.models import WorkflowReply

logger = logging.getLogger(__name__)


def list_user_conversations(user: WebChatUser, *, limit: int = 20) -> list[WebChatConversationSummary]:
    """현재 사용자의 대화 목록을 최신 순으로 반환한다."""
    summaries = list_conversations(user.user_id, limit=limit)
    return [_to_web_summary(summary) for summary in summaries]


def get_conversation_messages(
    user: WebChatUser,
    conversation_id: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """현재 사용자의 특정 대화 메시지 이력을 반환한다."""
    _ensure_valid_conversation_id(conversation_id)
    return get_history(user.user_id, conversation_id=conversation_id, limit=limit)


def send_web_chat_message(
    user: WebChatUser,
    conversation_id: str,
    text: str,
) -> WebChatReply:
    """사용자 메시지를 저장하고 LangGraph 워크플로를 실행해 응답을 돌려준다.

    워크플로 실패 시 assistant 메시지는 저장하지 않아 이중 저장을 방지한다.
    """
    _ensure_valid_conversation_id(conversation_id)
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise BadRequest("Message must not be empty.")

    message_id = f"web:{uuid.uuid4().hex}"

    try:
        append_message(
            user.user_id,
            {"role": "user", "content": cleaned_text},
            conversation_id=conversation_id,
            metadata={
                "channel_id": conversation_id,
                "source": "web",
                "direction": "inbound",
                "user_name": user.user_name,
                "message_id": message_id,
            },
        )
    except ConversationStoreError:
        log_activity(
            "web_chat_store_failed",
            level="ERROR",
            user_id=user.user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            stage="inbound",
        )
        raise

    incoming = CubeIncomingMessage(
        user_id=user.user_id,
        user_name=user.user_name,
        channel_id=conversation_id,
        message_id=message_id,
        message=cleaned_text,
    )

    log_activity(
        "web_chat_message_received",
        user_id=user.user_id,
        user_name=user.user_name,
        conversation_id=conversation_id,
        message_id=message_id,
        message_length=len(cleaned_text),
    )

    reply = _run_workflow(incoming)

    try:
        append_message(
            user.user_id,
            {"role": "assistant", "content": reply.reply},
            conversation_id=conversation_id,
            metadata={
                "channel_id": conversation_id,
                "source": "web",
                "direction": "outbound",
                "user_name": user.user_name,
                "reply_to_message_id": message_id,
                "workflow_id": reply.workflow_id,
            },
        )
    except ConversationStoreError:
        log_activity(
            "web_chat_store_failed",
            level="ERROR",
            user_id=user.user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            stage="outbound",
        )

    log_activity(
        "web_chat_reply_sent",
        user_id=user.user_id,
        user_name=user.user_name,
        conversation_id=conversation_id,
        message_id=message_id,
        reply_length=len(reply.reply or ""),
        workflow_id=reply.workflow_id,
    )

    return WebChatReply(
        conversation_id=conversation_id,
        message_id=message_id,
        reply=reply.reply,
        workflow_id=reply.workflow_id,
    )


def _run_workflow(incoming: CubeIncomingMessage) -> WorkflowReply:
    try:
        return handle_message(incoming)
    except Exception:
        log_activity(
            "web_chat_workflow_failed",
            level="ERROR",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            conversation_id=incoming.channel_id,
            message_id=incoming.message_id,
        )
        logger.exception("web_chat workflow handle_message failed")
        raise


def _ensure_valid_conversation_id(conversation_id: str) -> None:
    if not conversation_id or not conversation_id.strip():
        raise BadRequest("conversation_id must not be empty.")


def _to_web_summary(summary: ConversationSummary) -> WebChatConversationSummary:
    return WebChatConversationSummary(
        conversation_id=summary.conversation_id,
        last_message_at=summary.last_message_at,
        last_message_role=summary.last_message_role,
        last_message_preview=summary.last_message_preview,
        source=summary.source,
    )
