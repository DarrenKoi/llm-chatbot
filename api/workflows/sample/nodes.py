"""샘플 번역 워크플로 노드.

누락된 정보가 있으면 사용자에게 다시 질문하고, 충분한 정보가 모이면
MCP 번역 도구를 호출한다.
"""

from __future__ import annotations

import logging
import re

from api.mcp.executor import execute_tool_call
from api.mcp.models import MCPToolCall
from api.workflows.models import NodeResult
from api.workflows.sample.state import SampleWorkflowState

log = logging.getLogger(__name__)

_LANGUAGE_ALIASES = {
    "english": "en",
    "eng": "en",
    "en": "en",
    "영어": "en",
    "일본어": "ja",
    "일어": "ja",
    "japanese": "ja",
    "japan": "ja",
    "ja": "ja",
}
_LANGUAGE_LABELS = {
    "en": "영어",
    "ja": "일본어",
}
_QUOTED_TEXT_PATTERN = re.compile(r"""["']([^"']+)["']""")


def entry_node(state: SampleWorkflowState, user_message: str) -> NodeResult:
    """초기 번역 요청에서 문장과 목표 언어를 최대한 추출한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_source_text_node(state: SampleWorkflowState, user_message: str) -> NodeResult:
    """번역할 원문을 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_target_language_node(state: SampleWorkflowState, user_message: str) -> NodeResult:
    """목표 언어를 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def translate_node(state: SampleWorkflowState, user_message: str) -> NodeResult:
    """MCP translate 도구를 호출해 결과를 반환한다."""

    del user_message

    source_text = state.source_text or state.data.get("source_text", "")
    target_language = state.target_language or state.data.get("target_language", "")

    log.info("[sample] translate 도구 호출: text=%s target_language=%s", source_text, target_language)
    result = execute_tool_call(
        MCPToolCall(
            tool_id="translate",
            arguments={
                "text": source_text,
                "target_language": target_language,
            },
        )
    )
    log.info("[sample] translate 도구 결과: %s", result)

    translated = result.output.get("result", "") if isinstance(result.output, dict) else ""
    source_language = ""
    direction = ""
    if isinstance(result.output, dict):
        source_language = result.output.get("source", "")
        direction = f"{source_language}→{result.output.get('target', '')}"

    return NodeResult(
        action="complete",
        reply=translated,
        data_updates={
            "source_language": source_language,
            "translation_direction": direction,
            "translated": translated,
            "last_asked_slot": "",
        },
    )


def _resolve_translation_request(state: SampleWorkflowState, user_message: str) -> NodeResult:
    source_text = state.source_text or state.data.get("source_text", "")
    target_language = state.target_language or state.data.get("target_language", "")

    parsed_source_text, parsed_target_language = _parse_translation_request(user_message)
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
    lowered = user_message.lower()
    for alias, language_code in _LANGUAGE_ALIASES.items():
        if alias in lowered:
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

    for alias in sorted(_LANGUAGE_ALIASES, key=len, reverse=True):
        cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"[?.,!]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if target_language:
        label = _LANGUAGE_LABELS.get(target_language, "")
        if cleaned == label:
            return ""

    return cleaned
