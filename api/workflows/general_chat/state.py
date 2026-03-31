"""일반 대화 워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass(slots=True)
class GeneralChatWorkflowState(WorkflowState):
    """자유 대화와 fallback 라우팅에 필요한 상태다."""

    detected_intent: str = "general_chat"
    retrieved_contexts: list[str] = field(default_factory=list)
    agent_plan: list[str] = field(default_factory=list)
