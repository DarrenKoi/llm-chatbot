"""여행 계획 샘플 워크플로 패키지."""


def build_lg_graph():
    """travel_planner 서브그래프 빌더를 반환한다."""

    from api.workflows.travel_planner.lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """travel_planner 워크플로 정의를 반환한다."""

    from api.workflows.travel_planner.lg_adapter import build_graph
    from api.workflows.travel_planner.state import TravelPlannerState

    return {
        "workflow_id": "travel_planner",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "build_lg_graph": build_lg_graph,
        "state_cls": TravelPlannerState,
        "handoff_keywords": (
            "travel plan",
            "trip plan",
            "trip planner",
            "travel planner",
            "여행 계획",
            "여행 일정",
            "여행 플랜",
        ),
    }
