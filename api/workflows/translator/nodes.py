"""번역 서비스 워크플로 노드."""

import logging

from api.mcp.executor import execute_tool_call
from api.mcp.models import MCPToolCall
from api.workflows.models import NodeResult
from api.workflows.translator.llm_decision import decide_translation_turn
from api.workflows.translator.state import TranslatorWorkflowState

log = logging.getLogger(__name__)


def entry_node(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    """초기 번역 요청에서 다음 액션을 판단한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_source_text_node(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    """번역할 원문을 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def collect_target_language_node(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    """목표 언어를 다시 수집한다."""

    return _resolve_translation_request(state=state, user_message=user_message)


def translate_node(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    """MCP translate 도구를 호출해 결과를 반환한다."""

    del user_message

    source_text = state.source_text
    target_language = state.target_language

    log.info("[translator] translate 도구 호출: text=%s target_language=%s", source_text, target_language)
    result = execute_tool_call(
        MCPToolCall(
            tool_id="translate",
            arguments={
                "text": source_text,
                "target_language": target_language,
            },
        )
    )
    log.info("[translator] translate 도구 결과: %s", result)

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


def _resolve_translation_request(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    decision = decide_translation_turn(
        user_message=user_message,
        source_text=state.source_text,
        target_language=state.target_language,
        last_asked_slot=state.last_asked_slot,
        status=state.status,
    )

    if decision.action == "end_conversation":
        return NodeResult(
            action="complete",
            reply=decision.reply,
            next_node_id="entry",
            data_updates={
                "source_text": "",
                "source_language": "",
                "target_language": "",
                "translated": "",
                "pronunciation_ko": "",
                "translation_direction": "",
                "last_asked_slot": "",
            },
        )

    if decision.action == "ask_user":
        return NodeResult(
            action="wait",
            reply=decision.reply,
            next_node_id=(
                "collect_target_language" if decision.missing_slot == "target_language" else "collect_source_text"
            ),
            data_updates={
                "source_text": decision.source_text,
                "target_language": decision.target_language,
                "last_asked_slot": decision.missing_slot,
            },
        )

    return NodeResult(
        action="resume",
        next_node_id="translate",
        data_updates={
            "source_text": decision.source_text,
            "target_language": decision.target_language,
            "last_asked_slot": "",
        },
    )
