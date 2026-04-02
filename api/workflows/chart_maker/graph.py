"""차트 생성 워크플로 그래프 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.chart_maker import nodes, routing


def build_graph() -> dict[str, object]:
    """차트 생성 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "chart_maker",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_requirements": nodes.collect_requirements_node,
            "build_spec": nodes.build_spec_node,
        },
        "edges": [
            ("entry", "collect_requirements"),
            ("collect_requirements", "build_spec"),
        ],
        "router": routing.route_next_node,
    }
