"""시작 대화용 응답 계획기 스텁을 제공한다."""

from api.workflows.start_chat.state import StartChatWorkflowState


def plan_start_chat_response(*, user_message: str, state: StartChatWorkflowState) -> list[str]:
    """사용자 메시지에 대한 간단한 응답 계획을 만든다."""

    del state
    return [f"answer:{user_message}"]
