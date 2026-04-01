"""샘플 워크플로 그래프를 정의한다."""

from api.workflows.sample import nodes


def build_graph() -> dict[str, object]:
    """entry → greet(도구호출) → shout(도구호출) → 완료."""

    return {
        "workflow_id": "sample",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "greet": nodes.greet_node,
            "shout": nodes.shout_node,
        },
    }
