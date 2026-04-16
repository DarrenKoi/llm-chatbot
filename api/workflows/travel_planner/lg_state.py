"""여행 계획 워크플로 전용 상태 정의."""

from api.workflows.lg_state import ChatState


class TravelPlannerState(ChatState, total=False):
    """여행 계획 워크플로 전용 상태."""

    destination: str
    travel_style: str
    duration_text: str
    companion_type: str
    suggested_destinations: list[str]
    recommended_places: list[str]
    last_asked_slot: str
