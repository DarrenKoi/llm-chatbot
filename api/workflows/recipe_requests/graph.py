"""레시피 요청 워크플로 그래프 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.recipe_requests import nodes, routing


def build_graph() -> dict[str, object]:
    """레시피 요청 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "recipe_requests",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_slots": nodes.collect_slots_node,
            "confirm_request": nodes.confirm_request_node,
        },
        "edges": [
            ("entry", "collect_slots"),
            ("collect_slots", "confirm_request"),
        ],
        "router": routing.route_next_node,
    }
