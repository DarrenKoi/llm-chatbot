"""AT wafer quota 워크플로 그래프 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.at_wafer_quota import nodes, routing


def build_graph() -> dict[str, object]:
    """AT wafer quota 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "at_wafer_quota",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "fetch_quota": nodes.fetch_quota_node,
            "decide_next_action": nodes.decide_next_action_node,
        },
        "router": routing.route_next_node,
    }
