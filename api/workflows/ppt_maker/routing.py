"""프레젠테이션 생성 워크플로 라우팅 규칙 스텁을 정의한다."""

from api.workflows.models import NodeResult
from api.workflows.ppt_maker.state import PptMakerWorkflowState


def route_next_node(state: PptMakerWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def should_collect_template(state: PptMakerWorkflowState) -> bool:
    """템플릿 첨부 수집이 필요한지 판단한다."""

    return state.template_path is None
