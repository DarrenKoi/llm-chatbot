"""레시피 요청 워크플로 전용 상태를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass(slots=True)
class RecipeRequestsWorkflowState(WorkflowState):
    """레시피 요청 slot-filling에 필요한 상태다."""

    recipe_type: str = ""
    material_info: dict[str, str] = field(default_factory=dict)
    process_conditions: dict[str, str] = field(default_factory=dict)
