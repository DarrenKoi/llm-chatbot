"""공용 서브워크플로 라우팅 규칙 스텁을 정의한다."""

from api.workflows.common.state import CommonWorkflowState
from api.workflows.models import NodeResult


def route_next_node(state: CommonWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def should_resume_parent(state: CommonWorkflowState) -> bool:
    """부모 워크플로로 복귀할지 여부를 판단한다."""

    return bool(state.stack) and state.status == "completed"
