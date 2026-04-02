"""레시피 요청 워크플로 라우팅 규칙 스텁을 정의한다."""

from api.workflows.models import NodeResult
from api.workflows.recipe_requests.state import RecipeRequestsWorkflowState


def route_next_node(state: RecipeRequestsWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def has_required_slots(state: RecipeRequestsWorkflowState) -> bool:
    """필수 슬롯 수집 완료 여부를 판단한다."""

    return bool(state.recipe_type)
