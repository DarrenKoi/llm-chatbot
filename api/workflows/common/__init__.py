"""공용 서브워크플로 패키지."""


def get_workflow_definition() -> dict[str, object]:
    """공용 워크플로 정의를 반환한다."""

    from api.workflows.common.graph import build_graph
    from api.workflows.common.state import CommonWorkflowState

    return {
        "workflow_id": "common",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": CommonWorkflowState,
    }
