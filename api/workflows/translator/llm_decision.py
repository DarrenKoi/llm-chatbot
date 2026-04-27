"""LLM-driven decision layer for the translator workflow."""

import json
import logging
import re
from dataclasses import dataclass

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.intent_utils import is_stop_conversation_message
from api.workflows.translator.prompts import (
    TRANSLATOR_DECISION_SYSTEM_PROMPT,
    TRANSLATOR_DECISION_USER_PROMPT_PREFIX,
)
from api.workflows.translator.translation_engine import LANGUAGE_ALIASES

log = logging.getLogger(__name__)

_ASK_SOURCE_REPLY = '번역할 문장을 알려주세요. 예: "안녕하세요"\n원하시면 "취소"라고 말씀하셔도 됩니다.'
_STOP_REPLY = "번역은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."

_LANGUAGE_LABELS = {
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "es": "스페인어",
    "fr": "프랑스어",
    "de": "독일어",
    "vi": "베트남어",
    "th": "태국어",
}
_TARGET_LANGUAGES = set(_LANGUAGE_LABELS)
_ASK_TARGET_REPLY = (
    f"어떤 언어로 번역할까요? {', '.join(_LANGUAGE_LABELS.values())} 중 하나를 말씀해주세요.\n"
    '원하시면 문장과 언어를 함께 다시 보내거나 "취소"라고 말씀하셔도 됩니다.'
)
# Drop ≤2-char ASCII aliases from the fallback regex matcher: short codes like
# "de", "es", "fr", "th", "vi" collide with ordinary words in user text and
# would otherwise be stripped out by _extract_source_text.
_TARGET_LANGUAGE_ALIASES = {
    k: v for k, v in LANGUAGE_ALIASES.items() if v in _TARGET_LANGUAGES and not (k.isascii() and len(k) <= 2)
}
_TARGET_LANGUAGE_ALIASES_SORTED = sorted(_TARGET_LANGUAGE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
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
            system_prompt=TRANSLATOR_DECISION_SYSTEM_PROMPT,
            user_prompt=(
                TRANSLATOR_DECISION_USER_PROMPT_PREFIX + json.dumps(state_payload, ensure_ascii=False, indent=2)
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
    return _TARGET_LANGUAGE_ALIASES.get(normalized, "")


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
    for alias, language_code in _TARGET_LANGUAGE_ALIASES_SORTED:
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

    for alias, _ in _TARGET_LANGUAGE_ALIASES_SORTED:
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
