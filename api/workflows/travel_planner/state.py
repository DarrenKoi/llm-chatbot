"""여행 계획 샘플 워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass
class TravelPlannerState(WorkflowState):
    """여행 목적지, 선호도, 일정 정보를 유지한다."""

    destination: str = ""
    travel_style: str = ""
    duration_text: str = ""
    companion_type: str = ""
    suggested_destinations: list[str] = field(default_factory=list)
    recommended_places: list[str] = field(default_factory=list)
    last_asked_slot: str = ""
