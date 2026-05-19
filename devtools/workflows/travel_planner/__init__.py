"""dev runner 여행 플래너 워크플로.

start_chat 핸드오프 검증에서 사용하는 실제 dev workflow ID다. 현재 구현은
``travel_planner_example``의 규칙 기반 그래프를 재사용해 LLM 없이 로컬에서
분기와 멀티턴 흐름을 확인할 수 있게 한다.
"""


def build_lg_graph():
    """travel_planner LangGraph 빌더를 반환한다."""

    from devtools.workflows.travel_planner_example import build_lg_graph as builder

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
