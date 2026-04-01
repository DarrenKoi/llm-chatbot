"""시작 대화 워크플로 전용 상태를 정의한다."""

from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass
class StartChatWorkflowState(WorkflowState):
    """의도 분류와 일반 대화 처리에 필요한 상태다."""

    detected_intent: str = "start_chat"
    retrieved_contexts: list[str] = field(default_factory=list)
    agent_plan: list[str] = field(default_factory=list)
