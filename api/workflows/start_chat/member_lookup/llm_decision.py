"""사내 구성원 조회 여부를 판단하는 LLM 결정 레이어."""

import json
import logging
from dataclasses import dataclass, field

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.start_chat.member_lookup.prompts import (
    MEMBER_LOOKUP_DECISION_SYSTEM_PROMPT,
    MEMBER_LOOKUP_DECISION_USER_PROMPT_PREFIX,
)

log = logging.getLogger(__name__)

_ALLOWED_FILTER_KEYS = ("dept", "part", "campus", "work_place", "work_group", "level", "text")


@dataclass
class MemberLookupDecision:
    needs_lookup: bool = False
    mode: str = "search"
    query: str = ""
    filters: dict[str, str] = field(default_factory=dict)


def decide_member_lookup(user_message: str) -> MemberLookupDecision:
    """메시지가 사람/담당 질의인지 LLM으로 판단하고 검색어를 추출한다.

    LLM 실패 시 needs_lookup=False로 폴백한다(조회 생략 → 평소대로 답변).
    """

    message = (user_message or "").strip()
    if not message:
        return MemberLookupDecision()

    payload = {"latest_user_message": message}
    try:
        raw = generate_json_reply(
            system_prompt=MEMBER_LOOKUP_DECISION_SYSTEM_PROMPT,
            user_prompt=MEMBER_LOOKUP_DECISION_USER_PROMPT_PREFIX + json.dumps(payload, ensure_ascii=False, indent=2),
        )
    except LLMServiceError:
        log.warning("member_lookup LLM 결정 실패 — 조회 생략")
        return MemberLookupDecision()

    return _coerce_decision(raw)


def _coerce_decision(raw: dict[str, object]) -> MemberLookupDecision:
    needs_lookup = bool(raw.get("needs_lookup"))
    if not needs_lookup:
        return MemberLookupDecision()

    mode = str(raw.get("mode", "search")).strip().lower()
    if mode not in ("search", "filter"):
        mode = "search"

    query = str(raw.get("query", "")).strip()

    raw_filters = raw.get("filters")
    filters: dict[str, str] = {}
    if isinstance(raw_filters, dict):
        for key in _ALLOWED_FILTER_KEYS:
            value = raw_filters.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                filters[key] = text

    # filter 모드인데 필터도 query도 없으면 검색 불가 → 조회 생략
    if mode == "filter" and not filters and not query:
        return MemberLookupDecision()
    if mode == "search" and not query:
        return MemberLookupDecision()

    return MemberLookupDecision(needs_lookup=True, mode=mode, query=query, filters=filters)
