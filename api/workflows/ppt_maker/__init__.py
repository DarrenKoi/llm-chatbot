"""프레젠테이션 생성 워크플로 패키지."""


def get_workflow_definition() -> dict[str, object]:
    """ppt_maker 워크플로 정의를 반환한다."""

    from api.workflows.ppt_maker.graph import build_graph
    from api.workflows.ppt_maker.state import PptMakerWorkflowState

    return {
        "workflow_id": "ppt_maker",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": PptMakerWorkflowState,
        "handoff_keywords": (
            "ppt",
            "powerpoint",
            "power point",
            "slide",
            "slides",
            "deck",
            "슬라이드",
            "발표자료",
            "프레젠테이션",
        ),
    }
