"""여행 계획 예제 LangGraph 워크플로."""

import logging
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.travel_planner.constants import (
    DESTINATION_DEFAULT_STYLE,
    DESTINATION_TO_PLACES,
    build_companion_note,
    recommend_destinations,
)
from api.workflows.travel_planner.llm_decision import CANCEL_GUIDE_REPLY, decide_travel_planner_turn

from .lg_state import TravelPlannerExampleState

log = logging.getLogger(__name__)


def resolve_node(state: TravelPlannerExampleState) -> dict:
    """사용자 메시지에서 여행 정보를 추출해 상태를 갱신한다."""

    decision = decide_travel_planner_turn(
        user_message=state.get("user_message", ""),
        destination=state.get("destination", ""),
        travel_style=state.get("travel_style", ""),
        duration_text=state.get("duration_text", ""),
        companion_type=state.get("companion_type", ""),
        last_asked_slot=state.get("last_asked_slot", ""),
        status=state.get("status", "active"),
    )

    if decision.action == "end_conversation":
        return {
            "messages": [AIMessage(content=decision.reply)],
            "destination": "",
            "travel_style": "",
            "duration_text": "",
            "companion_type": "",
            "suggested_destinations": [],
            "recommended_places": [],
            "last_asked_slot": "",
            "conversation_ended": True,
        }

    log.info(
        "[travel_planner_example] LLM 판단: action=%s destination=%s style=%s duration=%s companion=%s",
        decision.action,
        decision.destination,
        decision.travel_style,
        decision.duration_text,
        decision.companion_type,
    )

    return {
        "destination": decision.destination,
        "travel_style": decision.travel_style,
        "duration_text": decision.duration_text,
        "companion_type": decision.companion_type,
        "last_asked_slot": decision.missing_slot if decision.action == "ask_user" else "",
        "pending_reply": decision.reply if decision.action == "ask_user" else "",
        "conversation_ended": False,
    }


def collect_preference_node(state: TravelPlannerExampleState) -> dict:
    """여행 스타일을 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "travel_style"}


def recommend_destination_node(state: TravelPlannerExampleState) -> dict:
    """여행 스타일 기반 목적지 후보를 추천하고 선택을 기다린다."""

    style = state.get("travel_style", "")
    companion = state.get("companion_type", "")
    suggestions = recommend_destinations(style=style)

    log.info(
        "[travel_planner_example] 목적지 후보 추천: style=%s companion=%s suggestions=%s",
        style,
        companion,
        suggestions,
    )

    companion_text = f"{companion}와 함께 가는 일정이라면 " if companion else ""
    reply = (
        f"{companion_text}{style} 여행으로는 {', '.join(suggestions)}를 먼저 고려해보세요.\n"
        "마음에 드는 곳을 하나 골라 말씀해주시면 그 목적지 기준으로 일정과 방문지를 추천해드릴게요.\n"
        f"{CANCEL_GUIDE_REPLY}"
    )

    user_input = interrupt({"reply": reply})
    return {
        "user_message": user_input,
        "suggested_destinations": suggestions,
        "last_asked_slot": "destination",
    }


def collect_trip_context_node(state: TravelPlannerExampleState) -> dict:
    """일정(기간)을 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "duration_text"}


def build_plan_node(state: TravelPlannerExampleState) -> dict:
    """선택된 목적지 기준으로 여행 계획안을 생성한다."""

    destination = state.get("destination", "")
    duration_text = state.get("duration_text", "")
    travel_style = state.get("travel_style") or DESTINATION_DEFAULT_STYLE.get(destination, "도시")
    companion_type = state.get("companion_type", "")

    recommended_places = DESTINATION_TO_PLACES.get(destination, [])[:3]
    note = build_companion_note(companion_type)
    reply_lines = [
        f"{destination} {duration_text} 여행은 {travel_style} 중심으로 시작하면 좋습니다.",
    ]
    if recommended_places:
        reply_lines.append(f"추천 방문지: {', '.join(recommended_places)}")
    if len(recommended_places) >= 3:
        reply_lines.append(
            f"추천 흐름: 첫날은 {recommended_places[0]} 주변, "
            f"다음 일정은 {recommended_places[1]}와 {recommended_places[2]}를 묶어보세요."
        )
    reply_lines.append(note)
    reply_lines.append("원하시면 다음 단계에서 숙소 지역이나 일자별 상세 동선도 이어서 정리할 수 있습니다.")
    reply = "\n".join(reply_lines)

    log.info(
        "[travel_planner_example] 계획 생성 완료: destination=%s duration=%s style=%s companion=%s",
        destination,
        duration_text,
        travel_style,
        companion_type,
    )

    return {
        "messages": [AIMessage(content=reply)],
        "travel_style": travel_style,
        "recommended_places": recommended_places,
        "last_asked_slot": "",
    }


def _route_after_resolve(
    state: TravelPlannerExampleState,
) -> Literal["collect_preference", "recommend_destination", "collect_trip_context", "build_plan", "__end__"]:
    if state.get("conversation_ended"):
        return END
    if state.get("last_asked_slot") == "travel_style":
        return "collect_preference"
    if state.get("last_asked_slot") == "duration_text":
        return "collect_trip_context"
    if not state.get("destination"):
        if not state.get("travel_style"):
            return "collect_preference"
        return "recommend_destination"
    if not state.get("duration_text"):
        return "collect_trip_context"
    return "build_plan"


def build_lg_graph() -> StateGraph:
    """여행 계획 예제 LangGraph StateGraph 빌더를 반환한다."""

    builder = StateGraph(TravelPlannerExampleState)

    builder.add_node("resolve", resolve_node)
    builder.add_node("collect_preference", collect_preference_node)
    builder.add_node("recommend_destination", recommend_destination_node)
    builder.add_node("collect_trip_context", collect_trip_context_node)
    builder.add_node("build_plan", build_plan_node)

    builder.set_entry_point("resolve")
    builder.add_conditional_edges("resolve", _route_after_resolve)
    builder.add_edge("collect_preference", "resolve")
    builder.add_edge("recommend_destination", "resolve")
    builder.add_edge("collect_trip_context", "resolve")
    builder.add_edge("build_plan", END)

    return builder
