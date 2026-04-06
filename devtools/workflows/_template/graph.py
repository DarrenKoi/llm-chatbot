"""__WORKFLOW_ID__ 워크플로 그래프를 정의한다."""

from . import nodes


def build_graph() -> dict[str, object]:
    """워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "__WORKFLOW_ID__",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
        },
        "edges": [],
    }
