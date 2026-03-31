"""일반 대화 워크플로 라우팅 규칙 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.general_chat.state import GeneralChatWorkflowState
from api.workflows.models import NodeResult


def route_next_node(state: GeneralChatWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def determine_handoff_workflow(state: GeneralChatWorkflowState) -> str | None:
    """일반 대화에서 다른 업무 워크플로로 넘길 대상을 판단한다."""

    handoff_map = {
        "chart_maker": "chart_maker",
        "ppt_maker": "ppt_maker",
        "at_wafer_quota": "at_wafer_quota",
        "recipe_requests": "recipe_requests",
    }
    return handoff_map.get(state.detected_intent)
