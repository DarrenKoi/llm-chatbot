"""MCP 도구 호출을 검증하기 위한 샘플 워크플로 패키지."""

from __future__ import annotations


def get_workflow_definition() -> dict[str, object]:
    """sample 워크플로 정의를 반환한다."""

    from api.workflows.sample.graph import build_graph
    from api.workflows.sample.state import SampleWorkflowState

    return {
        "workflow_id": "sample",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": SampleWorkflowState,
    }
