"""LLM-driven decision layer for the travel planner workflow."""

import json
import logging
import re
from dataclasses import dataclass

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.intent_utils import is_stop_conversation_message

log = logging.getLogger(__name__)

CANCEL_GUIDE_REPLY = '중간에 그만하고 싶으시면 "취소"라고 말씀해주세요.'

_ASK_STYLE_REPLY = (
    f"여행 계획을 같이 잡아볼게요. 어떤 스타일의 여행을 원하시나요?\n예: 도시, 휴양, 자연, 먹거리\n{CANCEL_GUIDE_REPLY}"
)
_ASK_DURATION_REPLY = f"일정은 며칠인가요? 예: 2박 3일\n{CANCEL_GUIDE_REPLY}"
_STOP_REPLY = "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."

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
_DESTINATION_ALIASES_SORTED = sorted(_DESTINATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
_STYLE_ALIASES_SORTED = sorted(_STYLE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
_COMPANION_ALIASES_SORTED = sorted(_COMPANION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
_DURATION_PATTERN = re.compile(r"(?:(\d+)\s*박\s*(\d+)\s*일)|(\d+)\s*일")
_WORKFLOW_SYSTEM_PROMPT = """
당신은 여행 계획 워크플로를 제어하는 판단기입니다.
최신 사용자 메시지와 현재 상태를 보고 다음 행동만 결정하세요.

반드시 JSON 객체 하나만 반환하세요. 키는 아래 7개만 사용하세요.
- action: "ask_user" | "recommend_destination" | "build_plan" | "end_conversation"
- destination: 문자열
- travel_style: 문자열
- duration_text: 문자열
- companion_type: 문자열
- missing_slot: "travel_style" | "duration_text" | ""
- reply: 사용자에게 보낼 한국어 문장. recommend_destination/build_plan일 때는 빈 문자열

판단 규칙:
- 사용자가 stop, bye, 취소, 그만, 끝, 종료처럼 대화를 마치려는 뜻이면 action은 end_conversation
- 최신 메시지에 새 여행 요청이 있으면 이전 상태보다 최신 요청을 우선
- 목적지가 없고 여행 스타일도 없으면 ask_user + missing_slot=travel_style
- 목적지는 없지만 여행 스타일이 있으면 recommend_destination
- 목적지가 있고 기간이 없으면 ask_user + missing_slot=duration_text
- 목적지와 기간이 있으면 build_plan
- companion_type은 선택 정보이며 있으면 유지하거나 갱신
- reply는 짧고 자연스러운 한국어로 작성
- destination, travel_style, duration_text, companion_type은 표준화된 값으로 넣으세요.
""".strip()


@dataclass
class TravelPlannerTurnDecision:
    action: str
    destination: str = ""
    travel_style: str = ""
    duration_text: str = ""
    companion_type: str = ""
    missing_slot: str = ""
    reply: str = ""


def decide_travel_planner_turn(
    *,
    user_message: str,
    destination: str = "",
    travel_style: str = "",
    duration_text: str = "",
    companion_type: str = "",
    last_asked_slot: str = "",
    status: str = "active",
) -> TravelPlannerTurnDecision:
    """Use the configured LLM to decide the next travel planner action."""

    state_payload = {
        "status": status,
        "last_asked_slot": last_asked_slot,
        "destination": destination,
        "travel_style": travel_style,
        "duration_text": duration_text,
        "companion_type": companion_type,
        "latest_user_message": user_message,
    }

    try:
        raw_decision = generate_json_reply(
            system_prompt=_WORKFLOW_SYSTEM_PROMPT,
            user_prompt=(
                "현재 여행 계획 워크플로 상태를 보고 다음 행동을 판단하세요.\n"
                f"{json.dumps(state_payload, ensure_ascii=False, indent=2)}"
            ),
        )
        return _coerce_decision(
            raw_decision,
            destination=destination,
            travel_style=travel_style,
            duration_text=duration_text,
            companion_type=companion_type,
        )
    except LLMServiceError:
        log.exception("travel planner LLM decision failed; falling back to rule-based resolution")
        return _fallback_travel_planner_turn(
            user_message=user_message,
            destination=destination,
            travel_style=travel_style,
            duration_text=duration_text,
            companion_type=companion_type,
        )


def _coerce_decision(
    raw_decision: dict[str, object],
    *,
    destination: str,
    travel_style: str,
    duration_text: str,
    companion_type: str,
) -> TravelPlannerTurnDecision:
    action = str(raw_decision.get("action", "")).strip().lower()
    resolved_destination = _normalize_alias(raw_decision.get("destination", ""), _DESTINATION_ALIASES)
    resolved_style = _normalize_alias(raw_decision.get("travel_style", ""), _STYLE_ALIASES)
    resolved_duration = _normalize_duration(raw_decision.get("duration_text", ""))
    resolved_companion = _normalize_alias(raw_decision.get("companion_type", ""), _COMPANION_ALIASES)
    missing_slot = str(raw_decision.get("missing_slot", "")).strip()
    reply = str(raw_decision.get("reply", "")).strip()

    merged_destination = resolved_destination or destination
    merged_style = resolved_style or travel_style
    merged_duration = resolved_duration or duration_text
    merged_companion = resolved_companion or companion_type

    if action == "end_conversation":
        return TravelPlannerTurnDecision(action="end_conversation", reply=reply or _STOP_REPLY)

    if action == "build_plan" and merged_destination and merged_duration:
        return TravelPlannerTurnDecision(
            action="build_plan",
            destination=merged_destination,
            travel_style=merged_style,
            duration_text=merged_duration,
            companion_type=merged_companion,
        )

    if action == "recommend_destination" and merged_style and not merged_destination:
        return TravelPlannerTurnDecision(
            action="recommend_destination",
            travel_style=merged_style,
            duration_text=merged_duration,
            companion_type=merged_companion,
        )

    normalized_missing_slot = _normalize_missing_slot(
        missing_slot,
        destination=merged_destination,
        travel_style=merged_style,
        duration_text=merged_duration,
    )

    if merged_destination and merged_duration:
        return TravelPlannerTurnDecision(
            action="build_plan",
            destination=merged_destination,
            travel_style=merged_style,
            duration_text=merged_duration,
            companion_type=merged_companion,
        )

    if not merged_destination and merged_style:
        return TravelPlannerTurnDecision(
            action="recommend_destination",
            travel_style=merged_style,
            duration_text=merged_duration,
            companion_type=merged_companion,
        )

    return TravelPlannerTurnDecision(
        action="ask_user",
        destination=merged_destination,
        travel_style=merged_style,
        duration_text=merged_duration,
        companion_type=merged_companion,
        missing_slot=normalized_missing_slot,
        reply=reply or _default_reply_for_missing_slot(normalized_missing_slot, destination=merged_destination),
    )


def _normalize_missing_slot(
    missing_slot: str,
    *,
    destination: str,
    travel_style: str,
    duration_text: str,
) -> str:
    if missing_slot in {"travel_style", "duration_text"}:
        return missing_slot
    if not destination and not travel_style:
        return "travel_style"
    if destination and not duration_text:
        return "duration_text"
    return ""


def _default_reply_for_missing_slot(missing_slot: str, *, destination: str) -> str:
    if missing_slot == "duration_text":
        if destination:
            return f"{destination} 좋습니다. 일정은 며칠인가요? 예: 2박 3일\n{CANCEL_GUIDE_REPLY}"
        return _ASK_DURATION_REPLY
    return _ASK_STYLE_REPLY


def _normalize_alias(raw_value: object, aliases: dict[str, str]) -> str:
    return aliases.get(str(raw_value).strip().lower(), "")


def _normalize_duration(raw_value: object) -> str:
    value = str(raw_value).strip()
    if not value:
        return ""
    return _extract_duration(value)


def _fallback_travel_planner_turn(
    *,
    user_message: str,
    destination: str,
    travel_style: str,
    duration_text: str,
    companion_type: str,
) -> TravelPlannerTurnDecision:
    if is_stop_conversation_message(user_message):
        return TravelPlannerTurnDecision(action="end_conversation", reply=_STOP_REPLY)

    resolved_destination = destination
    resolved_style = travel_style
    resolved_duration = duration_text
    resolved_companion = companion_type

    parsed_destination, parsed_style, parsed_duration, parsed_companion = _parse_request(user_message)
    if parsed_destination:
        resolved_destination = parsed_destination
    if parsed_style:
        resolved_style = parsed_style
    if parsed_duration:
        resolved_duration = parsed_duration
    if parsed_companion:
        resolved_companion = parsed_companion

    if not resolved_destination and not resolved_style:
        return TravelPlannerTurnDecision(
            action="ask_user",
            destination=resolved_destination,
            travel_style=resolved_style,
            duration_text=resolved_duration,
            companion_type=resolved_companion,
            missing_slot="travel_style",
            reply=_ASK_STYLE_REPLY,
        )

    if not resolved_destination:
        return TravelPlannerTurnDecision(
            action="recommend_destination",
            travel_style=resolved_style,
            duration_text=resolved_duration,
            companion_type=resolved_companion,
        )

    if not resolved_duration:
        return TravelPlannerTurnDecision(
            action="ask_user",
            destination=resolved_destination,
            travel_style=resolved_style,
            duration_text=resolved_duration,
            companion_type=resolved_companion,
            missing_slot="duration_text",
            reply=_default_reply_for_missing_slot("duration_text", destination=resolved_destination),
        )

    return TravelPlannerTurnDecision(
        action="build_plan",
        destination=resolved_destination,
        travel_style=resolved_style,
        duration_text=resolved_duration,
        companion_type=resolved_companion,
    )


def _parse_request(user_message: str) -> tuple[str, str, str, str]:
    normalized = user_message.strip()
    destination = _match_alias(normalized, _DESTINATION_ALIASES_SORTED)
    travel_style = _match_alias(normalized, _STYLE_ALIASES_SORTED)
    duration_text = _extract_duration(normalized)
    companion_type = _match_alias(normalized, _COMPANION_ALIASES_SORTED)
    return destination, travel_style, duration_text, companion_type


def _match_alias(user_message: str, sorted_aliases: list[tuple[str, str]]) -> str:
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
