"""시작 대화 워크플로 패키지 — 모든 대화의 진입점."""

from __future__ import annotations


def get_workflow_definition() -> dict[str, object]:
    """start_chat 워크플로 정의를 반환한다."""

    from api.workflows.start_chat.graph import build_graph
    from api.workflows.start_chat.state import StartChatWorkflowState

    return {
        "workflow_id": "start_chat",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": StartChatWorkflowState,
    }
