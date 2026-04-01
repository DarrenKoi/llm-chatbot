"""시작 대화 워크플로 라우팅 규칙을 정의한다."""

from api.workflows.start_chat.state import StartChatWorkflowState
from api.workflows.models import NodeResult


def route_next_node(state: StartChatWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def determine_handoff_workflow(state: StartChatWorkflowState) -> str | None:
    """시작 대화에서 다른 업무 워크플로로 넘길 대상을 판단한다."""

    handoff_map = {
        "chart_maker": "chart_maker",
        "ppt_maker": "ppt_maker",
        "at_wafer_quota": "at_wafer_quota",
        "recipe_requests": "recipe_requests",
    }
    intent = getattr(state, "detected_intent", state.data.get("detected_intent", ""))
    return handoff_map.get(intent)
