"""일반 대화용 실행기 스텁을 제공한다."""

from __future__ import annotations

from api.workflows.general_chat.state import GeneralChatWorkflowState


def execute_general_chat_plan(*, user_message: str, state: GeneralChatWorkflowState) -> str:
    """계획 결과를 바탕으로 임시 응답을 만든다."""

    if state.retrieved_contexts:
        return f"일반 대화 스켈레톤 응답: {user_message}"
    return f"일반 대화 초안 응답: {user_message}"
