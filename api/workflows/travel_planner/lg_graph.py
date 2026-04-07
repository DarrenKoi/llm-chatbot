"""여행 계획 LangGraph 워크플로.

기존 커스텀 그래프(graph.py)와 동일한 동작을 LangGraph StateGraph로 구현한다.
resolve → 조건부 라우팅 → 수집/추천/계획 생성 흐름이다.
"""

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.lg_state import TravelPlannerState as LGTravelPlannerState
from api.workflows.travel_planner.nodes import (
    _build_companion_note,
    _parse_request,
    _recommend_destinations,
)

log = logging.getLogger(__name__)

_DESTINATION_DEFAULT_STYLE = {
    "서울": "도시",
    "부산": "먹거리",
    "제주": "휴양",
    "도쿄": "도시",
    "오사카": "먹거리",
    "교토": "자연",
    "타이베이": "먹거리",
    "방콕": "휴양",
    "싱가포르": "도시",
}

_DESTINATION_TO_PLACES = {
    "서울": ["경복궁", "북촌한옥마을", "성수동", "한강공원"],
    "부산": ["해운대", "광안리", "감천문화마을", "자갈치시장"],
    "제주": ["함덕해변", "성산일출봉", "협재해변", "동문시장"],
    "도쿄": ["시부야", "아사쿠사", "메이지신궁", "긴자"],
    "오사카": ["도톤보리", "오사카성", "우메다", "신세카이"],
    "교토": ["후시미 이나리 신사", "기요미즈데라", "아라시야마", "니시키시장"],
    "타이베이": ["타이베이 101", "중정기념당", "스린 야시장", "용캉제"],
    "방콕": ["왓 아룬", "아이콘시암", "짜뚜짝 시장", "차오프라야 강변"],
    "싱가포르": ["마리나 베이", "가든스 바이 더 베이", "하지 레인", "센토사"],
}


def resolve_node(state: LGTravelPlannerState) -> dict:
    """사용자 메시지에서 여행 정보를 추출해 상태를 갱신한다."""

    user_message = state.get("user_message", "")
    current_destination = state.get("destination", "")
    current_style = state.get("travel_style", "")
    current_duration = state.get("duration_text", "")
    current_companion = state.get("companion_type", "")

    parsed_dest, parsed_style, parsed_duration, parsed_companion = _parse_request(user_message)

    if parsed_dest:
        current_destination = parsed_dest
    if parsed_style:
        current_style = parsed_style
    if parsed_duration:
        current_duration = parsed_duration
    if parsed_companion:
        current_companion = parsed_companion

    log.info(
        "[travel_planner] 요청 해석: destination=%s style=%s duration=%s companion=%s message=%s",
        current_destination,
        current_style,
        current_duration,
        current_companion,
        user_message,
    )

    return {
        "destination": current_destination,
        "travel_style": current_style,
        "duration_text": current_duration,
        "companion_type": current_companion,
    }


def collect_preference_node(state: LGTravelPlannerState) -> dict:
    """여행 스타일을 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt(
        {"reply": "여행 계획을 같이 잡아볼게요. 어떤 스타일의 여행을 원하시나요?\n예: 도시, 휴양, 자연, 먹거리"}
    )
    return {"user_message": user_input, "last_asked_slot": "travel_style"}


def recommend_destination_node(state: LGTravelPlannerState) -> dict:
    """여행 스타일 기반 목적지 후보를 추천하고 선택을 기다린다."""

    style = state.get("travel_style", "")
    companion = state.get("companion_type", "")
    suggestions = _recommend_destinations(style=style)

    log.info("[travel_planner] 목적지 후보 추천: style=%s companion=%s suggestions=%s", style, companion, suggestions)

    companion_text = f"{companion}와 함께 가는 일정이라면 " if companion else ""
    reply = (
        f"{companion_text}{style} 여행으로는 {', '.join(suggestions)}를 먼저 고려해보세요.\n"
        "마음에 드는 곳을 하나 골라 말씀해주시면 그 목적지 기준으로 일정과 방문지를 추천해드릴게요."
    )

    user_input = interrupt({"reply": reply})
    return {
        "user_message": user_input,
        "suggested_destinations": suggestions,
        "last_asked_slot": "destination",
    }


def collect_trip_context_node(state: LGTravelPlannerState) -> dict:
    """일정(기간)을 사용자에게 요청하고 응답을 수집한다."""

    destination = state.get("destination", "")
    user_input = interrupt({"reply": f"{destination} 좋습니다. 일정은 며칠인가요? 예: 2박 3일"})
    return {"user_message": user_input, "last_asked_slot": "duration_text"}


def build_plan_node(state: LGTravelPlannerState) -> dict:
    """선택된 목적지 기준으로 여행 계획안을 생성한다."""

    destination = state.get("destination", "")
    duration_text = state.get("duration_text", "")
    travel_style = state.get("travel_style") or _DESTINATION_DEFAULT_STYLE.get(destination, "도시")
    companion_type = state.get("companion_type", "")

    recommended_places = _DESTINATION_TO_PLACES.get(destination, [])[:3]
    note = _build_companion_note(companion_type)
    reply_lines = [
        f"{destination} {duration_text} 여행은 {travel_style} 중심으로 시작하면 좋습니다.",
        f"추천 방문지: {', '.join(recommended_places)}",
        (
            f"추천 흐름: 첫날은 {recommended_places[0]} 주변, "
            f"다음 일정은 {recommended_places[1]}와 {recommended_places[2]}를 묶어보세요."
        ),
        note,
        "원하시면 다음 단계에서 숙소 지역이나 일자별 상세 동선도 이어서 정리할 수 있습니다.",
    ]
    reply = "\n".join(reply_lines)

    log.info(
        "[travel_planner] 계획 생성 완료: destination=%s duration=%s style=%s companion=%s",
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


def _route_after_resolve(state: LGTravelPlannerState) -> str:
    """resolve 후 다음 노드를 결정한다."""

    if not state.get("destination"):
        if not state.get("travel_style"):
            return "collect_preference"
        return "recommend_destination"
    if not state.get("duration_text"):
        return "collect_trip_context"
    return "build_plan"


def build_lg_graph() -> StateGraph:
    """여행 계획 워크플로 LangGraph StateGraph 빌더를 반환한다."""

    builder = StateGraph(LGTravelPlannerState)

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
