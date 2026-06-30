"""사내 구성원/담당 질의를 감지해 member_info 결과를 컨텍스트로 주입하는 노드.

흐름: retrieve_context → **member_lookup** → generate_reply
트리거: (1) 명령어 override(`!담당` 등) (2) 키워드 게이트 통과 후 LLM 자동 감지.
결과는 retrieved_contexts에 블록으로 append되며 generate_reply_node가 LLM에 전달한다.
member_info 비활성/미설정·결과 없음·예외 시 무동작({})으로 평소 응답을 보장한다.
"""

import logging

from api import config
from api.member_info import filter_members, normalize_record, search_members
from api.workflows.start_chat.lg_state import StartChatState
from api.workflows.start_chat.member_lookup.llm_decision import (
    MemberLookupDecision,
    decide_member_lookup,
)
from api.workflows.start_chat.member_lookup.prompts import (
    COMMAND_TOKENS,
    KEYWORD_GATE,
    MEMBER_CONTEXT_HEADER,
)

log = logging.getLogger(__name__)


def _is_member_info_active() -> bool:
    return bool(config.MEMBER_INFO_ENABLED and config.MEMBER_INFO_BASE_URL)


def _strip_command(user_message: str) -> str | None:
    """명령어 접두어로 시작하면 나머지를 검색어로 반환한다. 아니면 None."""

    stripped = user_message.strip()
    lowered = stripped.lower()
    for token in COMMAND_TOKENS:
        if lowered.startswith(token.lower()):
            return stripped[len(token) :].strip()
    return None


def _passes_keyword_gate(user_message: str) -> bool:
    return any(keyword in user_message for keyword in KEYWORD_GATE)


def member_lookup_node(state: StartChatState) -> dict:
    """사람/담당 질의면 member_info를 조회해 retrieved_contexts에 블록을 추가한다."""

    user_message = state.get("user_message", "").strip()
    if not user_message or not _is_member_info_active():
        return {}

    decision = _resolve_decision(user_message)
    if decision is None or not decision.needs_lookup:
        return {}

    try:
        members = _run_lookup(decision)
    except Exception:
        log.exception("member_info 조회 실패 — 컨텍스트 없이 진행")
        return {}

    if not members:
        return {}

    block = _format_members(members)
    if not block:
        return {}

    contexts = list(state.get("retrieved_contexts", []))
    contexts.append(block)
    return {"retrieved_contexts": contexts}


def _resolve_decision(user_message: str) -> MemberLookupDecision | None:
    """명령어 override 우선, 없으면 키워드 게이트 통과 시 LLM 자동 감지."""

    command_query = _strip_command(user_message)
    if command_query is not None:
        if not command_query:
            return None
        return MemberLookupDecision(needs_lookup=True, mode="search", query=command_query)

    if not _passes_keyword_gate(user_message):
        return None
    return decide_member_lookup(user_message)


def _run_lookup(decision: MemberLookupDecision) -> list[dict]:
    if decision.mode == "filter" and decision.filters:
        return filter_members(**decision.filters)
    return search_members(decision.query)


def _format_members(members: list[dict]) -> str:
    """구성원 목록을 LLM 컨텍스트 블록 문자열로 만든다."""

    lines: list[str] = []
    for member in members:
        record = normalize_record(member)
        if not record:
            continue
        lines.append("- " + _format_record(record))

    if not lines:
        return ""
    return MEMBER_CONTEXT_HEADER + "\n" + "\n".join(lines)


def _format_record(record: dict) -> str:
    parts: list[str] = []

    name = record.get("name")
    if name:
        parts.append(name)

    group = " / ".join(value for value in (record.get("dept"), record.get("part")) if value)
    if group:
        parts.append(group)

    if record.get("job"):
        parts.append(record["job"])

    if record.get("responsibility"):
        parts.append(f"담당: {record['responsibility']}")

    if config.MEMBER_INFO_INCLUDE_CONTACT:
        contact = " / ".join(value for value in (record.get("office_tel"), record.get("mobile_tel")) if value)
        if contact:
            parts.append(f"☎ {contact}")

    return " | ".join(parts)
