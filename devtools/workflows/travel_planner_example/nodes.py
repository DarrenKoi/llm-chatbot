"""여행 계획 예제 워크플로 노드.

`api/workflows/travel_planner`와 같은 흐름으로 작성된 devtools 예제다.
상태 추출 -> 재질문 -> 추천 -> 완료 패턴을 그대로 참고할 수 있다.
"""

import logging
import re

from api.workflows.models import NodeResult
from api.workflows.travel_planner.llm_decision import decide_travel_planner_turn

from .state import TravelPlannerExampleState

log = logging.getLogger(__name__)

_DESTINATION_ALIASES = {
    "서울": "서울",
    "seoul": "서울",
    "부산": "부산",
    "busan": "부산",
    "제주": "제주",
    "제주도": "제주",
    "jeju": "제주",
    "도쿄": "도쿄",
    "tokyo": "도쿄",
    "오사카": "오사카",
    "osaka": "오사카",
    "교토": "교토",
    "kyoto": "교토",
    "타이베이": "타이베이",
    "taipei": "타이베이",
    "방콕": "방콕",
    "bangkok": "방콕",
    "싱가포르": "싱가포르",
    "singapore": "싱가포르",
}

_STYLE_ALIASES = {
    "도시": "도시",
    "city": "도시",
    "휴양": "휴양",
    "힐링": "휴양",
    "휴식": "휴양",
    "relax": "휴양",
    "자연": "자연",
    "nature": "자연",
    "먹거리": "먹거리",
    "맛집": "먹거리",
    "food": "먹거리",
}

_COMPANION_ALIASES = {
    "혼자": "혼자",
    "solo": "혼자",
    "친구": "친구",
    "friends": "친구",
    "가족": "가족",
    "family": "가족",
    "연인": "연인",
    "커플": "연인",
    "couple": "연인",
}

_STYLE_TO_DESTINATIONS = {
    "도시": ["서울", "도쿄", "싱가포르"],
    "휴양": ["제주", "방콕", "싱가포르"],
    "자연": ["제주", "교토", "부산"],
    "먹거리": ["오사카", "타이베이", "부산"],
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

_DURATION_PATTERN = re.compile(r"(?:(\d+)\s*박\s*(\d+)\s*일)|(\d+)\s*일")


def _sorted_aliases(aliases: dict[str, str]) -> list[tuple[str, str]]:
    return sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True)


_DESTINATION_ALIASES_SORTED = _sorted_aliases(_DESTINATION_ALIASES)
_STYLE_ALIASES_SORTED = _sorted_aliases(_STYLE_ALIASES)
_COMPANION_ALIASES_SORTED = _sorted_aliases(_COMPANION_ALIASES)


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
    suggestions = _recommend_destinations(style=style)

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
        '원하시면 "취소"라고 말씀하셔도 됩니다.'
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
    travel_style = state.travel_style or _DESTINATION_DEFAULT_STYLE.get(destination, "도시")
    companion_type = state.companion_type

    recommended_places = _DESTINATION_TO_PLACES.get(destination, [])[:3]
    note = _build_companion_note(companion_type)
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


def _parse_request(user_message: str) -> tuple[str, str, str, str]:
    normalized = user_message.strip()
    destination = _match_alias(normalized, _DESTINATION_ALIASES_SORTED)
    travel_style = _match_alias(normalized, _STYLE_ALIASES_SORTED)
    duration_text = _extract_duration(normalized)
    companion_type = _match_alias(normalized, _COMPANION_ALIASES_SORTED)
    return destination, travel_style, duration_text, companion_type


def _match_alias(user_message: str, sorted_aliases: list[tuple[str, str]]) -> str:
    """사전 정렬된 별칭 목록에서 첫 번째 매칭 값을 반환한다."""

    lowered = user_message.lower()
    for alias, canonical in sorted_aliases:
        if alias.lower() in lowered:
            return canonical
    return ""


def _extract_duration(user_message: str) -> str:
    match = _DURATION_PATTERN.search(user_message)
    if not match:
        return ""

    nights, days, days_only = match.groups()
    if nights and days:
        return f"{nights}박 {days}일"
    return f"{days_only}일"


def _recommend_destinations(*, style: str) -> list[str]:
    if style in _STYLE_TO_DESTINATIONS:
        return list(_STYLE_TO_DESTINATIONS[style])
    return ["서울", "제주", "도쿄"]


def _build_companion_note(companion_type: str) -> str:
    if companion_type == "가족":
        return "가족 여행이라면 이동 횟수를 줄이고 휴식 가능한 장소를 중간에 끼워 넣는 편이 좋습니다."
    if companion_type == "연인":
        return "연인 여행이라면 야경이나 산책 코스를 한 구간 넣으면 만족도가 높습니다."
    if companion_type == "친구":
        return "친구 여행이라면 맛집과 야간 활동을 한 구간 포함하면 일정이 덜 단조롭습니다."
    if companion_type == "혼자":
        return "혼자 여행이라면 동선을 단순하게 잡고 오래 머물 곳을 1~2곳 정하는 편이 편합니다."
    return "동행 정보가 없어 일반 여행자 기준으로 무난한 동선으로 추천했습니다."
