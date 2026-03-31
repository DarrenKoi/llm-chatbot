"""공용 서브워크플로 노드 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.common.state import CommonWorkflowState
from api.workflows.models import NodeResult


def entry_node(state: CommonWorkflowState, user_message: str) -> NodeResult:
    """공용 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="verify_user")


def verify_user_node(state: CommonWorkflowState, user_message: str) -> NodeResult:
    """사용자 확인 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="confirm")


def confirm_node(state: CommonWorkflowState, user_message: str) -> NodeResult:
    """최종 확인 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="reply", reply="확인 절차 스켈레톤입니다.", next_node_id="done")


def collect_attachment_node(state: CommonWorkflowState, user_message: str) -> NodeResult:
    """첨부 수집 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="done")


def human_handoff_node(state: CommonWorkflowState, user_message: str) -> NodeResult:
    """사람 상담 전환 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="complete", reply="담당자 연결 워크플로 스켈레톤입니다.")
