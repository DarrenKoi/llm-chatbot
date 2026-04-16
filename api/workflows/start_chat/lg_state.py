"""시작 대화 워크플로 전용 상태 정의."""

from api.workflows.lg_state import ChatState


class StartChatState(ChatState, total=False):
    """시작 대화 워크플로 전용 상태."""

    active_workflow: str
    retrieved_contexts: list[str]
    profile_loaded: bool
    profile_source: str
    profile_summary: str
