"""LLM-driven decision layer for the travel planner workflow."""

import json
import logging
from dataclasses import dataclass

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.intent_utils import is_stop_conversation_message
from api.workflows.travel_planner.constants import (
    COMPANION_ALIASES,
    DESTINATION_ALIASES,
    STYLE_ALIASES,
    extract_duration,
    parse_request,
)
from api.workflows.travel_planner.prompts import (
    TRAVEL_PLANNER_DECISION_SYSTEM_PROMPT,
    TRAVEL_PLANNER_DECISION_USER_PROMPT_PREFIX,
)

log = logging.getLogger(__name__)

CANCEL_GUIDE_REPLY = '중간에 그만하고 싶으시면 "취소"라고 말씀해주세요.'

_ASK_STYLE_REPLY = (
    f"여행 계획을 같이 잡아볼게요. 어떤 스타일의 여행을 원하시나요?\n예: 도시, 휴양, 자연, 먹거리\n{CANCEL_GUIDE_REPLY}"
)
_ASK_DURATION_REPLY = f"일정은 며칠인가요? 예: 2박 3일\n{CANCEL_GUIDE_REPLY}"
_STOP_REPLY = "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."


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
            system_prompt=TRAVEL_PLANNER_DECISION_SYSTEM_PROMPT,
            user_prompt=(
                TRAVEL_PLANNER_DECISION_USER_PROMPT_PREFIX + json.dumps(state_payload, ensure_ascii=False, indent=2)
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
    resolved_destination = _normalize_alias(raw_decision.get("destination", ""), DESTINATION_ALIASES)
    resolved_style = _normalize_alias(raw_decision.get("travel_style", ""), STYLE_ALIASES)
    resolved_duration = _normalize_duration(raw_decision.get("duration_text", ""))
    resolved_companion = _normalize_alias(raw_decision.get("companion_type", ""), COMPANION_ALIASES)
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
    return extract_duration(value)


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

    parsed_destination, parsed_style, parsed_duration, parsed_companion = parse_request(user_message)
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
