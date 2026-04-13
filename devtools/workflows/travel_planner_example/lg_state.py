"""여행 계획 예제 워크플로 전용 LangGraph 상태를 정의한다."""

from api.workflows.lg_state import ChatState


class TravelPlannerExampleState(ChatState, total=False):
    """여행 목적지, 선호도, 일정 정보를 유지한다."""

    destination: str
    travel_style: str
    duration_text: str
    companion_type: str
    suggested_destinations: list[str]
    recommended_places: list[str]
    last_asked_slot: str
    pending_reply: str
    conversation_ended: bool
