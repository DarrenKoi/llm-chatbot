"""번역 서비스를 위한 워크플로 패키지."""

TRANSLATOR_TOOL_TAGS: tuple[str, ...] = ("translation", "language")


def build_lg_graph():
    """translator 서브그래프 빌더를 반환한다."""

    from api.workflows.translator.lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """translator 워크플로 정의를 반환한다."""

    from api.workflows.translator.lg_adapter import build_graph
    from api.workflows.translator.state import TranslatorWorkflowState

    return {
        "workflow_id": "translator",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "build_lg_graph": build_lg_graph,
        "state_cls": TranslatorWorkflowState,
        "tool_tags": TRANSLATOR_TOOL_TAGS,
        "handoff_keywords": ("translate", "translation", "번역", "통역"),
    }
