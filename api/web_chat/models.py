"""웹 채팅 API의 요청·응답 DTO 모델."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebChatUser:
    """LASTUSER cookie에서 도출된 현재 사용자 정보."""

    user_id: str
    user_name: str


@dataclass(frozen=True, slots=True)
class WebChatMessageRequest:
    """클라이언트가 보낸 메시지 전송 요청."""

    conversation_id: str
    message: str


@dataclass(frozen=True, slots=True)
class WebChatReply:
    """단일 메시지 송신 후 클라이언트에게 돌려줄 응답."""

    conversation_id: str
    message_id: str
    reply: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class WebChatConversationSummary:
    """대화 목록에 노출할 한 건의 요약."""

    conversation_id: str
    last_message_at: str
    last_message_role: str
    last_message_preview: str
    source: str | None
