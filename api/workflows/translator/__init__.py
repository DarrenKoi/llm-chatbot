"""번역 서비스를 위한 워크플로 패키지."""

TRANSLATOR_TOOL_TAGS: tuple[str, ...] = ("translation", "language")


def get_workflow_definition() -> dict[str, object]:
    """translator 워크플로 정의를 반환한다."""

    from api.workflows.translator.graph import build_graph
    from api.workflows.translator.state import TranslatorWorkflowState

    return {
        "workflow_id": "translator",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": TranslatorWorkflowState,
        "tool_tags": TRANSLATOR_TOOL_TAGS,
    }
