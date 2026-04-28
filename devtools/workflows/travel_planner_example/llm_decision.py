"""Deterministic decision helper for the devtools travel planner example."""

from dataclasses import dataclass

from devtools.workflows.intent_utils import is_stop_conversation_message

from .constants import parse_request

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
    """Resolve the next example turn with simple rule-based slot parsing."""

    del last_asked_slot, status

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
            reply=_default_duration_reply(resolved_destination),
        )

    return TravelPlannerTurnDecision(
        action="build_plan",
        destination=resolved_destination,
        travel_style=resolved_style,
        duration_text=resolved_duration,
        companion_type=resolved_companion,
    )


def _default_duration_reply(destination: str) -> str:
    if destination:
        return f"{destination} 좋습니다. 일정은 며칠인가요? 예: 2박 3일\n{CANCEL_GUIDE_REPLY}"
    return _ASK_DURATION_REPLY
