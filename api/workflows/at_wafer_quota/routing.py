"""AT wafer quota 워크플로 라우팅 규칙 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.at_wafer_quota.state import AtWaferQuotaWorkflowState
from api.workflows.models import NodeResult


def route_next_node(state: AtWaferQuotaWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def should_borrow_quota(state: AtWaferQuotaWorkflowState) -> bool:
    """quota borrow 절차가 필요한지 판단한다."""

    return state.requested_amount > state.quota_remaining
