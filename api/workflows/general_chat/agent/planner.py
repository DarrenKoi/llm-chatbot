"""일반 대화용 응답 계획기 스텁을 제공한다."""

from __future__ import annotations

from api.workflows.general_chat.state import GeneralChatWorkflowState


def plan_general_chat_response(*, user_message: str, state: GeneralChatWorkflowState) -> list[str]:
    """사용자 메시지에 대한 간단한 응답 계획을 만든다."""

    del state
    return [f"answer:{user_message}"]
