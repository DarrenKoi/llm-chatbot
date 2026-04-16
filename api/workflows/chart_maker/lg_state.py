"""차트 생성 워크플로 전용 상태 정의."""

from api.workflows.lg_state import ChatState


class ChartMakerState(ChatState, total=False):
    """차트 생성 워크플로 전용 상태."""

    chart_type: str
    data_fields: list[str]
    chart_spec: dict[str, str]
