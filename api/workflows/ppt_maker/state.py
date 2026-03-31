"""프레젠테이션 생성 워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from api.workflows.models import WorkflowState


@dataclass(slots=True)
class PptMakerWorkflowState(WorkflowState):
    """PPT 기획과 초안 생성에 필요한 상태다."""

    audience: str = ""
    tone: str = ""
    outline: list[str] = field(default_factory=list)
    template_path: Path | None = None
