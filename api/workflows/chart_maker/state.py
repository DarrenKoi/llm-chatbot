"""차트 생성 워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass(slots=True)
class ChartMakerWorkflowState(WorkflowState):
    """차트 요구사항 수집과 명세 생성에 필요한 상태다."""

    chart_type: str = ""
    data_fields: list[str] = field(default_factory=list)
    chart_spec: dict[str, str] = field(default_factory=dict)
