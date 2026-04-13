"""여행 계획 예제 워크플로 노드.

`api/workflows/travel_planner`와 같은 흐름으로 작성된 devtools 예제다.
상태 추출 -> 재질문 -> 추천 -> 완료 패턴을 그대로 참고할 수 있다.
"""

import logging

from api.workflows.models import NodeResult
from api.workflows.travel_planner.constants import (
    DESTINATION_DEFAULT_STYLE,
    DESTINATION_TO_PLACES,
    build_companion_note,
    recommend_destinations,
)
from api.workflows.travel_planner.llm_decision import CANCEL_GUIDE_REPLY, decide_travel_planner_turn

from .state import TravelPlannerExampleState

log = logging.getLogger(__name__)


def entry_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """첫 사용자 메시지에서 최대한 많은 여행 정보를 추출한다."""

    return _resolve_request(state=state, user_message=user_message)


def collect_preference_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """여행 스타일을 다시 수집한다."""

    return _resolve_request(state=state, user_message=user_message)


def collect_destination_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """추천 후보 중 목적지를 확정한다."""

    return _resolve_request(state=state, user_message=user_message)


def collect_trip_context_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """일정과 동행 정보를 다시 수집한다."""

    return _resolve_request(state=state, user_message=user_message)


def recommend_destination_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """여행 스타일을 바탕으로 시작 후보를 추천한다."""

    del user_message

    style = state.travel_style
    companion = state.companion_type
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
    return NodeResult(
        action="wait",
        reply=reply,
        next_node_id="collect_destination",
        data_updates={
            "suggested_destinations": suggestions,
            "last_asked_slot": "destination",
        },
    )


def build_plan_node(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    """선택된 목적지 기준으로 간단한 여행 시작안을 제안한다."""

    del user_message

    destination = state.destination
    duration_text = state.duration_text
    travel_style = state.travel_style or DESTINATION_DEFAULT_STYLE.get(destination, "도시")
    companion_type = state.companion_type

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

    return NodeResult(
        action="complete",
        reply=reply,
        next_node_id="entry",
        data_updates={
            "destination": destination,
            "travel_style": travel_style,
            "duration_text": duration_text,
            "companion_type": companion_type,
            "recommended_places": recommended_places,
            "last_asked_slot": "",
        },
    )


def _resolve_request(state: TravelPlannerExampleState, user_message: str) -> NodeResult:
    decision = decide_travel_planner_turn(
        user_message=user_message,
        destination=state.destination,
        travel_style=state.travel_style,
        duration_text=state.duration_text,
        companion_type=state.companion_type,
        last_asked_slot=state.last_asked_slot,
        status=state.status,
    )

    if decision.action == "end_conversation":
        return NodeResult(
            action="complete",
            reply=decision.reply,
            next_node_id="entry",
            data_updates={
                "destination": "",
                "travel_style": "",
                "duration_text": "",
                "companion_type": "",
                "suggested_destinations": [],
                "recommended_places": [],
                "last_asked_slot": "",
            },
        )

    log.info(
        "[travel_planner_example] LLM 판단: action=%s destination=%s style=%s duration=%s companion=%s message=%s",
        decision.action,
        decision.destination,
        decision.travel_style,
        decision.duration_text,
        decision.companion_type,
        user_message,
    )

    base_updates = {
        "destination": decision.destination,
        "travel_style": decision.travel_style,
        "duration_text": decision.duration_text,
        "companion_type": decision.companion_type,
    }

    if decision.action == "ask_user":
        return NodeResult(
            action="wait",
            reply=decision.reply,
            next_node_id=("collect_trip_context" if decision.missing_slot == "duration_text" else "collect_preference"),
            data_updates={**base_updates, "last_asked_slot": decision.missing_slot},
        )

    if decision.action == "recommend_destination":
        return NodeResult(
            action="resume",
            next_node_id="recommend_destination",
            data_updates={**base_updates, "last_asked_slot": ""},
        )

    return NodeResult(
        action="resume",
        next_node_id="build_plan",
        data_updates={**base_updates, "last_asked_slot": ""},
    )
