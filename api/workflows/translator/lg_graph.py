"""번역 서비스 LangGraph 워크플로.

기존 커스텀 그래프(graph.py)와 동일한 동작을 LangGraph StateGraph로 구현한다.
interrupt()를 사용해 누락 정보를 사용자에게 요청하고, 재개 시 이어서 번역을 수행한다.
"""

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.mcp.executor import execute_tool_call
from api.mcp.models import MCPToolCall
from api.workflows.lg_state import TranslatorState
from api.workflows.translator.nodes import _parse_translation_request

log = logging.getLogger(__name__)


def resolve_node(state: TranslatorState) -> dict:
    """사용자 메시지에서 번역 원문과 목표 언어를 추출한다."""

    user_message = state.get("user_message", "")
    previous_source_text = state.get("source_text", "")
    previous_target_language = state.get("target_language", "")
    last_asked_slot = state.get("last_asked_slot", "")

    parsed_source, parsed_target = _parse_translation_request(user_message)

    source_text = previous_source_text
    target_language = previous_target_language

    if last_asked_slot == "source_text":
        if parsed_source:
            source_text = parsed_source
    elif last_asked_slot == "target_language":
        if parsed_target:
            target_language = parsed_target
    else:
        if parsed_source:
            source_text = parsed_source
        if parsed_target:
            target_language = parsed_target

    return {
        "source_text": source_text,
        "target_language": target_language,
        "last_asked_slot": "",
    }


def collect_source_text_node(state: TranslatorState) -> dict:
    """번역할 원문을 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": '번역할 문장을 알려주세요. 예: "안녕하세요"'})
    return {"user_message": user_input, "last_asked_slot": "source_text"}


def collect_target_language_node(state: TranslatorState) -> dict:
    """목표 언어를 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": "어떤 언어로 번역할까요? 영어 또는 일본어 중 하나를 말씀해주세요."})
    return {"user_message": user_input, "last_asked_slot": "target_language"}


def translate_node(state: TranslatorState) -> dict:
    """MCP translate 도구를 호출해 결과를 반환한다."""

    source_text = state.get("source_text", "")
    target_language = state.get("target_language", "")

    log.info("[translator] translate 도구 호출: text=%s target_language=%s", source_text, target_language)
    result = execute_tool_call(
        MCPToolCall(
            tool_id="translate",
            arguments={"text": source_text, "target_language": target_language},
        )
    )
    log.info("[translator] translate 도구 결과: %s", result)

    translated = result.output.get("result", "") if isinstance(result.output, dict) else ""
    source_language = ""
    direction = ""
    pronunciation_ko = ""
    if isinstance(result.output, dict):
        source_language = result.output.get("source", "")
        direction = f"{source_language}\u2192{result.output.get('target', '')}"
        pronunciation_ko = result.output.get("pronunciation_ko", "")

    reply = translated
    if pronunciation_ko:
        reply = f"{translated}\n(한국어 발음: {pronunciation_ko})"

    return {
        "messages": [AIMessage(content=reply)],
        "source_language": source_language,
        "translation_direction": direction,
        "translated": translated,
        "pronunciation_ko": pronunciation_ko,
        "last_asked_slot": "",
    }


def _route_after_resolve(state: TranslatorState) -> str:
    """resolve 후 다음 노드를 결정한다."""

    if not state.get("source_text"):
        return "collect_source_text"
    if not state.get("target_language"):
        return "collect_target_language"
    return "translate"


def build_lg_graph() -> StateGraph:
    """번역 워크플로 LangGraph StateGraph 빌더를 반환한다.

    호출자가 ``builder.compile(checkpointer=...)``로 체크포인터를 주입한다.
    """

    builder = StateGraph(TranslatorState)

    builder.add_node("resolve", resolve_node)
    builder.add_node("collect_source_text", collect_source_text_node)
    builder.add_node("collect_target_language", collect_target_language_node)
    builder.add_node("translate", translate_node)

    builder.set_entry_point("resolve")
    builder.add_conditional_edges("resolve", _route_after_resolve)
    builder.add_edge("collect_source_text", "resolve")
    builder.add_edge("collect_target_language", "resolve")
    builder.add_edge("translate", END)

    return builder
