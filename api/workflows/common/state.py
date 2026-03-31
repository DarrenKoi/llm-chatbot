"""공용 서브워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from api.workflows.models import WorkflowState


@dataclass(slots=True)
class CommonWorkflowState(WorkflowState):
    """여러 업무 워크플로에서 재사용할 공통 상태다."""

    pending_action: str = ""
    confirmation_required: bool = False
    attachment_paths: list[Path] = field(default_factory=list)
