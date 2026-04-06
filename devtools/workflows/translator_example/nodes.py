"""번역 예제 워크플로 노드.

누락된 정보가 있으면 사용자에게 다시 질문하고, 충분한 정보가 모이면
devtools 예제용 MCP 번역 도구를 호출한다.
"""

import logging
import re

from api.mcp.executor import execute_tool_call
from api.mcp.models import MCPToolCall
from api.workflows.models import NodeResult

from .state import TranslatorExampleState

log = logging.getLogger(__name__)

_LANGUAGE_ALIASES = {
    "english": "en",
    "eng": "en",
    "영어": "en",
    "일본어": "ja",
    "일어": "ja",
    "japanese": "ja",
}
_LANGUAGE_LABELS = {
    "en": "영어",
    "ja": "일본어",
}
_LANGUAGE_ALIASES_SORTED = sorted(_LANGUAGE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
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


def entry_node(state: TranslatorExampleState, user_message: str) -> NodeResult:
    """초기 번역 요청에서 문장과 목표 언어를 최대한 추출한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_source_text_node(state: TranslatorExampleState, user_message: str) -> NodeResult:
    """번역할 원문을 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_target_language_node(state: TranslatorExampleState, user_message: str) -> NodeResult:
    """목표 언어를 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def translate_node(state: TranslatorExampleState, user_message: str) -> NodeResult:
    """예제용 MCP translate 도구를 호출해 결과를 반환한다."""

    del user_message

    source_text = state.source_text
    target_language = state.target_language

    log.info(
        "[translator_example] translate_example 도구 호출: text=%s target_language=%s",
        source_text,
        target_language,
    )
    result = execute_tool_call(
        MCPToolCall(
            tool_id="translate_example",
            arguments={
                "text": source_text,
                "target_language": target_language,
            },
        )
    )
    log.info("[translator_example] translate_example 도구 결과: %s", result)

    translated = result.output.get("result", "") if isinstance(result.output, dict) else ""
    source_language = ""
    direction = ""
    pronunciation_ko = ""
    if isinstance(result.output, dict):
        source_language = result.output.get("source", "")
        direction = f"{source_language}→{result.output.get('target', '')}"
        pronunciation_ko = result.output.get("pronunciation_ko", "")

    reply = translated
    if pronunciation_ko:
        reply = f"{translated}\n(한국어 발음: {pronunciation_ko})"

    return NodeResult(
        action="complete",
        reply=reply,
        next_node_id="entry",
        data_updates={
            "source_language": source_language,
            "translation_direction": direction,
            "translated": translated,
            "pronunciation_ko": pronunciation_ko,
            "last_asked_slot": "",
        },
    )


def _resolve_translation_request(state: TranslatorExampleState, user_message: str) -> NodeResult:
    previous_source_text = state.source_text
    previous_target_language = state.target_language
    last_asked_slot = state.last_asked_slot
    source_text = previous_source_text
    target_language = previous_target_language

    parsed_source_text, parsed_target_language = _parse_translation_request(user_message)

    if last_asked_slot == "source_text":
        if parsed_source_text:
            source_text = parsed_source_text
    elif last_asked_slot == "target_language":
        if parsed_target_language:
            target_language = parsed_target_language
    elif state.status == "completed":
        source_text = parsed_source_text
        target_language = parsed_target_language
        if not source_text and target_language and previous_source_text:
            source_text = previous_source_text
    else:
        if parsed_source_text:
            source_text = parsed_source_text
        if parsed_target_language:
            target_language = parsed_target_language

    data_updates = {
        "source_text": source_text,
        "target_language": target_language,
    }

    if not source_text:
        return NodeResult(
            action="wait",
            reply='번역할 문장을 알려주세요. 예: "안녕하세요"',
            next_node_id="collect_source_text",
            data_updates={**data_updates, "last_asked_slot": "source_text"},
        )

    if not target_language:
        return NodeResult(
            action="wait",
            reply="어떤 언어로 번역할까요? 영어 또는 일본어 중 하나를 말씀해주세요.",
            next_node_id="collect_target_language",
            data_updates={**data_updates, "last_asked_slot": "target_language"},
        )

    return NodeResult(
        action="resume",
        next_node_id="translate",
        data_updates={**data_updates, "last_asked_slot": ""},
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


_POSTPOSITIONS = r"(?:으로(?:도|는|만)?|로(?:도|는|만)?|를|은|는|의|에서|에|가|도|와|과)?"


def _build_language_alias_pattern(alias: str) -> str:
    if alias.isascii():
        return rf"\b{re.escape(alias)}\b"
    escaped = re.escape(alias)
    return rf"(?<![가-힣]){escaped}{_POSTPOSITIONS}(?![가-힣])"
