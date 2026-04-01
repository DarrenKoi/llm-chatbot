"""시작 대화용 실행기 스텁을 제공한다."""

from api.workflows.start_chat.state import StartChatWorkflowState


def execute_start_chat_plan(*, user_message: str, state: StartChatWorkflowState) -> str:
    """계획 결과를 바탕으로 임시 응답을 만든다."""

    if getattr(state, "retrieved_contexts", None) or state.data.get("retrieved_contexts"):
        return f"시작 대화 스켈레톤 응답: {user_message}"
    return f"시작 대화 초안 응답: {user_message}"
