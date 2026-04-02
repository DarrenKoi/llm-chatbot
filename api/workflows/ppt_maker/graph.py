"""프레젠테이션 생성 워크플로 그래프 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.ppt_maker import nodes, routing


def build_graph() -> dict[str, object]:
    """프레젠테이션 생성 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "ppt_maker",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_brief": nodes.collect_brief_node,
            "draft_outline": nodes.draft_outline_node,
        },
        "edges": [
            ("entry", "collect_brief"),
            ("collect_brief", "draft_outline"),
        ],
        "router": routing.route_next_node,
    }
