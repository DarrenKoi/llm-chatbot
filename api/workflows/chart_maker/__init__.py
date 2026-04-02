"""차트 생성 워크플로 패키지."""


def get_workflow_definition() -> dict[str, object]:
    """chart_maker 워크플로 정의를 반환한다."""

    from api.workflows.chart_maker.graph import build_graph
    from api.workflows.chart_maker.state import ChartMakerWorkflowState

    return {
        "workflow_id": "chart_maker",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": ChartMakerWorkflowState,
        "handoff_keywords": ("chart", "graph", "plot", "차트", "그래프", "시각화"),
    }
