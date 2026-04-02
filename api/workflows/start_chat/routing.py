"""시작 대화 워크플로 라우팅 규칙을 정의한다."""

from api.workflows.models import NodeResult
from api.workflows.start_chat.state import StartChatWorkflowState

_WORKFLOW_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("chart_maker", ("chart", "graph", "plot", "차트", "그래프", "시각화")),
    (
        "ppt_maker",
        ("ppt", "powerpoint", "power point", "slide", "slides", "deck", "슬라이드", "발표자료", "프레젠테이션"),
    ),
    ("at_wafer_quota", ("wafer", "quota", "at wafer", "웨이퍼", "쿼터", "할당량")),
    ("recipe_requests", ("recipe", "recipes", "formula", "레시피", "배합", "처방")),
)


def route_next_node(state: StartChatWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def detect_intent(state: StartChatWorkflowState, user_message: str) -> str:
    """현재 메시지와 상태를 바탕으로 다음 의도를 추정한다."""

    normalized = user_message.strip().lower()
    if not normalized:
        return getattr(state, "detected_intent", state.data.get("detected_intent", "start_chat"))

    for workflow_id, keywords in _WORKFLOW_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return workflow_id

    return "start_chat"


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
