"""여행 계획 예제 워크플로 그래프를 정의한다."""

from . import nodes


def build_graph() -> dict[str, object]:
    """여행 계획 예제 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "travel_planner_example",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_preference": nodes.collect_preference_node,
            "recommend_destination": nodes.recommend_destination_node,
            "collect_destination": nodes.collect_destination_node,
            "collect_trip_context": nodes.collect_trip_context_node,
            "build_plan": nodes.build_plan_node,
        },
        "edges": [
            ("entry", "collect_preference", "목적지와 스타일 모두 없음"),
            ("entry", "recommend_destination", "스타일만 있음"),
            ("entry", "collect_trip_context", "목적지는 있으나 일정 없음"),
            ("entry", "build_plan", "목적지와 일정 충분"),
            ("collect_preference", "recommend_destination", "스타일 수집 완료"),
            ("recommend_destination", "collect_destination", "추천 후보 제안"),
            ("collect_destination", "collect_trip_context", "목적지 선택"),
            ("collect_destination", "build_plan", "목적지와 일정 한 번에 입력"),
            ("collect_trip_context", "build_plan", "일정 수집 완료"),
            ("build_plan", "done", "계획 완료"),
        ],
    }
