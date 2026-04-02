"""차트 생성 워크플로 라우팅 규칙 스텁을 정의한다."""

from api.workflows.chart_maker.state import ChartMakerWorkflowState
from api.workflows.models import NodeResult


def route_next_node(state: ChartMakerWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def should_request_more_details(state: ChartMakerWorkflowState) -> bool:
    """입력 정보가 충분한지 판단한다."""

    return not bool(state.chart_type)
