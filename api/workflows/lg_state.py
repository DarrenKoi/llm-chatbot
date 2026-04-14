"""LangGraph 워크플로에서 사용하는 공유 상태 정의."""

from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class ChatState(TypedDict, total=False):
    """모든 LangGraph 워크플로가 공유하는 기본 상태."""

    messages: Annotated[list, add_messages]
    user_id: str
    channel_id: str
    user_message: str
    conversation_ended: bool
    pending_reply: str


class TranslatorState(ChatState, total=False):
    """번역 워크플로 전용 상태."""

    source_text: str
    source_language: str
    target_language: str
    last_asked_slot: str
    translation_direction: str
    translated: str
    pronunciation_ko: str


class ChartMakerState(ChatState, total=False):
    """차트 생성 워크플로 전용 상태."""

    chart_type: str
    data_fields: list[str]
    chart_spec: dict[str, str]


class TravelPlannerState(ChatState, total=False):
    """여행 계획 워크플로 전용 상태."""

    destination: str
    travel_style: str
    duration_text: str
    companion_type: str
    suggested_destinations: list[str]
    recommended_places: list[str]
    last_asked_slot: str


class StartChatState(ChatState, total=False):
    """시작 대화 워크플로 전용 상태."""

    active_workflow: str
    retrieved_contexts: list[str]
    profile_loaded: bool
    profile_source: str
    profile_summary: str
