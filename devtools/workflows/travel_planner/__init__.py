"""dev runner 여행 플래너 워크플로."""


def build_lg_graph():
    """travel_planner LangGraph 빌더를 반환한다."""

    from .lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """travel_planner 워크플로 정의를 반환한다."""

    return {
        "workflow_id": "travel_planner",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": (
            "여행",
            "여행 계획",
            "여행 플랜",
            "여행플랜",
            "travel",
            "trip",
            "planner",
        ),
    }
