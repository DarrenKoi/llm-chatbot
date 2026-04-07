"""워크플로 공통 상태와 노드 결과 계약을 정의한다."""

from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowStatus = Literal["active", "waiting_user_input", "completed", "cancelled"]
NodeAction = Literal["reply", "handoff", "resume", "complete", "wait"]


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


@dataclass
class NodeResult:
    """노드 실행 후 오케스트레이터에 반환하는 표준 결과다."""

    action: NodeAction
    reply: str = ""
    next_node_id: str | None = None
    next_workflow_id: str | None = None
    data_updates: dict[str, Any] = field(default_factory=dict)
