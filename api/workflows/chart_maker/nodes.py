"""차트 생성 워크플로 노드 스텁을 정의한다."""

from api.workflows.chart_maker.state import ChartMakerWorkflowState
from api.workflows.models import NodeResult


def entry_node(state: ChartMakerWorkflowState, user_message: str) -> NodeResult:
    """차트 생성 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="collect_requirements")


def collect_requirements_node(state: ChartMakerWorkflowState, user_message: str) -> NodeResult:
    """차트 요구사항 수집 노드 스텁이다."""

    del state
    return NodeResult(
        action="wait",
        next_node_id="build_spec",
        data_updates={"chart_type": user_message.strip()},
    )


def build_spec_node(state: ChartMakerWorkflowState, user_message: str) -> NodeResult:
    """차트 명세 생성 노드 스텁이다."""

    del user_message
    return NodeResult(
        action="reply",
        reply="차트 명세 생성 스켈레톤입니다.",
        next_node_id="done",
        data_updates={"chart_spec": {"chart_type": state.chart_type or "bar"}},
    )
