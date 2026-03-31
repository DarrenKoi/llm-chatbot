"""AT wafer quota 워크플로 노드 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.at_wafer_quota.state import AtWaferQuotaWorkflowState
from api.workflows.models import NodeResult


def entry_node(state: AtWaferQuotaWorkflowState, user_message: str) -> NodeResult:
    """AT wafer quota 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="fetch_quota")


def fetch_quota_node(state: AtWaferQuotaWorkflowState, user_message: str) -> NodeResult:
    """quota 조회 노드 스텁이다."""

    del state, user_message
    return NodeResult(
        action="wait",
        next_node_id="decide_next_action",
        data_updates={"quota_total": 100, "quota_remaining": 20},
    )


def decide_next_action_node(state: AtWaferQuotaWorkflowState, user_message: str) -> NodeResult:
    """quota 결과에 따른 후속 분기 노드 스텁이다."""

    del user_message
    reply = "quota가 충분합니다." if state.quota_remaining >= state.requested_amount else "borrow 절차가 필요합니다."
    return NodeResult(action="reply", reply=reply, next_node_id="done")
