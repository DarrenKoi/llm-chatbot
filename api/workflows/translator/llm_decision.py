"""LLM-driven decision layer for the translator workflow."""

import json
import logging
import re
from dataclasses import dataclass

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.intent_utils import is_stop_conversation_message

log = logging.getLogger(__name__)

_ASK_SOURCE_REPLY = '번역할 문장을 알려주세요. 예: "안녕하세요"\n원하시면 "취소"라고 말씀하셔도 됩니다.'
_ASK_TARGET_REPLY = (
    "어떤 언어로 번역할까요? 영어 또는 일본어 중 하나를 말씀해주세요.\n"
    '원하시면 문장과 언어를 함께 다시 보내거나 "취소"라고 말씀하셔도 됩니다.'
)
_STOP_REPLY = "번역은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."

_LANGUAGE_ALIASES = {
    "english": "en",
    "eng": "en",
    "en": "en",
    "영어": "en",
    "일본어": "ja",
    "일어": "ja",
    "japanese": "ja",
    "ja": "ja",
}
_LANGUAGE_ALIASES_SORTED = sorted(_LANGUAGE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
_LANGUAGE_LABELS = {
    "en": "영어",
    "ja": "일본어",
}
_QUOTED_TEXT_PATTERN = re.compile(r"""["']([^"']+)["']""")
_FOLLOW_UP_SOURCE_PATTERNS = (
    r"(?i)\bthis time\b",
    r"(?i)\bas well\b",
)
_FOLLOW_UP_SOURCE_TOKENS = {
    "again",
    "also",
    "aswell",
    "please",
    "pls",
    "plz",
    "then",
    "this",
    "time",
    "too",
    "version",
    "그럼",
    "그러면",
    "다시",
    "도",
    "또",
    "또는",
    "로도",
    "버전",
    "부탁드려요",
    "부탁드립니다",
    "부탁해",
    "부탁해요",
    "이번엔",
    "이번에는",
    "정도",
}
_POSTPOSITIONS = r"(?:으로(?:도|는|만)?|로(?:도|는|만)?|를|은|는|의|에서|에|가|도|와|과)?"
_WORKFLOW_SYSTEM_PROMPT = """
당신은 번역 워크플로를 제어하는 판단기입니다.
최신 사용자 메시지와 현재 상태를 보고 다음 행동만 결정하세요.

반드시 JSON 객체 하나만 반환하세요. 키는 아래 5개만 사용하세요.
- action: "translate" | "ask_user" | "end_conversation"
- source_text: 문자열
- target_language: "en" | "ja" | ""
- missing_slot: "source_text" | "target_language" | ""
- reply: 사용자에게 보낼 한국어 문장. translate일 때는 빈 문자열

판단 규칙:
- 사용자가 stop, bye, 취소, 그만, 끝, 종료처럼 대화를 마치려는 뜻이면 action은 end_conversation
- 사용자가 새 번역 요청을 완성형으로 말하면 이전 상태보다 최신 요청을 우선
- 사용자가 누락된 정보만 말하면 기존 상태와 합쳐서 판단
- source_text와 target_language가 모두 있으면 action은 translate
- 정보가 부족하면 action은 ask_user, missing_slot에는 다음에 물어볼 필드를 넣기
- 목표 언어는 영어와 일본어만 지원합니다. 다른 언어거나 불명확하면 target_language를 비우고 ask_user
- reply는 짧고 자연스러운 한국어로 작성
- source_text는 사용자가 실제로 번역하길 원하는 문장일 때만 채우고, 안내 문구나 stop 표현을 넣지 마세요.
""".strip()


@dataclass
class TranslationTurnDecision:
    action: str
    source_text: str = ""
    target_language: str = ""
    missing_slot: str = ""
    reply: str = ""


def decide_translation_turn(
    *,
    user_message: str,
    source_text: str = "",
    target_language: str = "",
    last_asked_slot: str = "",
    status: str = "active",
) -> TranslationTurnDecision:
    """Use the configured LLM to decide the next translator workflow action."""

    state_payload = {
        "status": status,
        "last_asked_slot": last_asked_slot,
        "source_text": source_text,
        "target_language": target_language,
        "latest_user_message": user_message,
    }

    try:
        raw_decision = generate_json_reply(
            system_prompt=_WORKFLOW_SYSTEM_PROMPT,
            user_prompt=(
                "현재 번역 워크플로 상태를 보고 다음 행동을 판단하세요.\n"
                f"{json.dumps(state_payload, ensure_ascii=False, indent=2)}"
            ),
        )
        return _coerce_decision(raw_decision, source_text=source_text, target_language=target_language)
    except LLMServiceError:
        log.exception("translator LLM decision failed; falling back to rule-based resolution")
        return _fallback_translation_turn(
            user_message=user_message,
            source_text=source_text,
            target_language=target_language,
            status=status,
        )


def _coerce_decision(
    raw_decision: dict[str, object],
    *,
    source_text: str,
    target_language: str,
) -> TranslationTurnDecision:
    action = str(raw_decision.get("action", "")).strip().lower()
    resolved_source = str(raw_decision.get("source_text", "")).strip()
    resolved_target = _normalize_target_language(raw_decision.get("target_language", ""))
    missing_slot = str(raw_decision.get("missing_slot", "")).strip()
    reply = str(raw_decision.get("reply", "")).strip()

    if action == "end_conversation":
        return TranslationTurnDecision(
            action="end_conversation",
            reply=reply or _STOP_REPLY,
        )

    if action == "translate":
        if resolved_source and resolved_target:
            return TranslationTurnDecision(
                action="translate",
                source_text=resolved_source,
                target_language=resolved_target,
            )
        action = "ask_user"

    if action != "ask_user":
        action = "ask_user"

    merged_source = resolved_source or source_text
    merged_target = resolved_target or target_language
    normalized_missing_slot = _normalize_missing_slot(
        missing_slot,
        source_text=merged_source,
        target_language=merged_target,
    )
    if merged_source and merged_target:
        return TranslationTurnDecision(
            action="translate",
            source_text=merged_source,
            target_language=merged_target,
        )

    return TranslationTurnDecision(
        action="ask_user",
        source_text=merged_source,
        target_language=merged_target,
        missing_slot=normalized_missing_slot,
        reply=reply or _default_reply_for_missing_slot(normalized_missing_slot),
    )


def _normalize_missing_slot(missing_slot: str, *, source_text: str, target_language: str) -> str:
    if missing_slot in {"source_text", "target_language"}:
        return missing_slot
    if not source_text:
        return "source_text"
    if not target_language:
        return "target_language"
    return ""


def _default_reply_for_missing_slot(missing_slot: str) -> str:
    if missing_slot == "target_language":
        return _ASK_TARGET_REPLY
    return _ASK_SOURCE_REPLY


def _normalize_target_language(raw_value: object) -> str:
    normalized = str(raw_value).strip().lower()
    return _LANGUAGE_ALIASES.get(normalized, "")


def _fallback_translation_turn(
    *,
    user_message: str,
    source_text: str,
    target_language: str,
    status: str,
) -> TranslationTurnDecision:
    if is_stop_conversation_message(user_message):
        return TranslationTurnDecision(
            action="end_conversation",
            reply=_STOP_REPLY,
        )

    resolved_source = source_text
    resolved_target = target_language
    parsed_source_text, parsed_target_language = _parse_translation_request(user_message)

    if parsed_source_text:
        resolved_source = parsed_source_text
    elif status == "completed" and parsed_target_language and source_text:
        resolved_source = source_text

    if parsed_target_language:
        resolved_target = parsed_target_language
    elif status == "completed" and parsed_source_text and target_language:
        resolved_target = target_language

    if not resolved_source:
        return TranslationTurnDecision(
            action="ask_user",
            target_language=resolved_target,
            missing_slot="source_text",
            reply=_ASK_SOURCE_REPLY,
        )

    if not resolved_target:
        return TranslationTurnDecision(
            action="ask_user",
            source_text=resolved_source,
            missing_slot="target_language",
            reply=_ASK_TARGET_REPLY,
        )

    return TranslationTurnDecision(
        action="translate",
        source_text=resolved_source,
        target_language=resolved_target,
    )


def _parse_translation_request(user_message: str) -> tuple[str, str]:
    stripped = user_message.strip()
    target_language = _extract_target_language(stripped)
    source_text = _extract_source_text(stripped, target_language=target_language)
    return source_text, target_language


def _extract_target_language(user_message: str) -> str:
    stripped = _QUOTED_TEXT_PATTERN.sub("", user_message)
    for alias, language_code in _LANGUAGE_ALIASES_SORTED:
        if re.search(_build_language_alias_pattern(alias), stripped, flags=re.IGNORECASE):
            return language_code
    return ""


def _extract_source_text(user_message: str, *, target_language: str) -> str:
    quoted_match = _QUOTED_TEXT_PATTERN.search(user_message)
    if quoted_match:
        return quoted_match.group(1).strip()

    cleaned = user_message
    cleaned = re.sub(r"(?i)\btranslate\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\binto\b", " ", cleaned)
    cleaned = re.sub(r"(?i)\bto\b", " ", cleaned)
    cleaned = re.sub(r"번역(해줘|해주세요|해 줘|해 주세요)?", " ", cleaned)
    cleaned = re.sub(r"바꿔(줘|주세요)?", " ", cleaned)

    for alias, _ in _LANGUAGE_ALIASES_SORTED:
        cleaned = re.sub(_build_language_alias_pattern(alias), " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[?.,!]", " ", cleaned)
    for pattern in _FOLLOW_UP_SOURCE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = " ".join(token for token in cleaned.split() if token.lower() not in _FOLLOW_UP_SOURCE_TOKENS).strip()

    if target_language:
        label = _LANGUAGE_LABELS.get(target_language, "")
        if cleaned == label:
            return ""

    return cleaned


def _build_language_alias_pattern(alias: str) -> str:
    if alias.isascii():
        return rf"\b{re.escape(alias)}\b"
    escaped = re.escape(alias)
    return rf"(?<![가-힣]){escaped}{_POSTPOSITIONS}(?![가-힣])"
