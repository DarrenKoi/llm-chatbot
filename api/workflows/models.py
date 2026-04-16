"""워크플로 공통 상태와 오케스트레이터 응답 모델을 정의한다."""

from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowStatus = Literal["active", "waiting_user_input", "completed", "cancelled"]


@dataclass
class WorkflowState:
    """오케스트레이터가 공통으로 다루는 워크플로 상태다."""

    user_id: str
    workflow_id: str
    node_id: str
    channel_id: str = ""
    status: WorkflowStatus = "active"
    data: dict[str, Any] = field(default_factory=dict)
    stack: list[dict[str, str]] = field(default_factory=list)


@dataclass
class WorkflowReply:
    """오케스트레이터가 Cube 서비스 계층에 반환하는 워크플로 실행 결과다."""

    reply: str
    workflow_id: str
