"""차트 생성 워크플로 패키지."""


def build_lg_graph():
    """chart_maker 서브그래프 빌더를 반환한다."""

    from api.workflows.chart_maker.lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """chart_maker 워크플로 정의를 반환한다."""

    from api.workflows.chart_maker.state import ChartMakerWorkflowState

    return {
        "workflow_id": "chart_maker",
        "build_lg_graph": build_lg_graph,
        "state_cls": ChartMakerWorkflowState,
        "handoff_keywords": ("chart", "graph", "plot", "차트", "그래프", "시각화"),
    }
