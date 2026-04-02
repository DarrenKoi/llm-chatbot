"""공용 서브워크플로 그래프 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.common import nodes, routing


def build_graph() -> dict[str, object]:
    """공용 서브워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "common",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "verify_user": nodes.verify_user_node,
            "confirm": nodes.confirm_node,
            "collect_attachment": nodes.collect_attachment_node,
            "human_handoff": nodes.human_handoff_node,
        },
        "edges": [
            ("entry", "verify_user"),
            ("verify_user", "confirm"),
            ("confirm", "collect_attachment"),
            ("collect_attachment", "human_handoff"),
        ],
        "router": routing.route_next_node,
    }
