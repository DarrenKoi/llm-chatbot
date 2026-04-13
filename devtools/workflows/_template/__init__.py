"""__WORKFLOW_ID__ 워크플로 패키지."""


def build_lg_graph():
    """__WORKFLOW_ID__ LangGraph 빌더를 반환한다."""

    from .lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """워크플로 정의를 반환한다."""

    return {
        "workflow_id": "__WORKFLOW_ID__",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": (),
    }
