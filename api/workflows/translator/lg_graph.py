"""번역 서비스 LangGraph 워크플로.

기존 커스텀 그래프(graph.py)와 동일한 동작을 LangGraph StateGraph로 구현한다.
interrupt()를 사용해 누락 정보를 사용자에게 요청하고, 재개 시 이어서 번역을 수행한다.
"""

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.translator.lg_state import TranslatorState
from api.workflows.translator.llm_decision import decide_translation_turn
from api.workflows.translator.translation_engine import execute_translation

log = logging.getLogger(__name__)


def resolve_node(state: TranslatorState) -> dict:
    """사용자 메시지에서 번역 원문과 목표 언어를 추출한다."""

    decision = decide_translation_turn(
        user_message=state.get("user_message", ""),
        source_text=state.get("source_text", ""),
        target_language=state.get("target_language", ""),
        last_asked_slot=state.get("last_asked_slot", ""),
        status=state.get("status", "active"),
    )

    if decision.action == "end_conversation":
        return {
            "messages": [AIMessage(content=decision.reply)],
            "source_text": "",
            "source_language": "",
            "target_language": "",
            "translation_direction": "",
            "translated": "",
            "pronunciation_ko": "",
            "last_asked_slot": "",
            "conversation_ended": True,
        }

    return {
        "source_text": decision.source_text,
        "target_language": decision.target_language,
        "last_asked_slot": decision.missing_slot if decision.action == "ask_user" else "",
        "pending_reply": decision.reply if decision.action == "ask_user" else "",
        "conversation_ended": False,
    }


def collect_source_text_node(state: TranslatorState) -> dict:
    """번역할 원문을 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "source_text"}


def collect_target_language_node(state: TranslatorState) -> dict:
    """목표 언어를 사용자에게 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "target_language"}


def translate_node(state: TranslatorState) -> dict:
    """MCP translate 도구를 호출해 결과를 반환한다."""

    result = execute_translation(state.get("source_text", ""), state.get("target_language", ""))

    if not result.success:
        return {
            "messages": [AIMessage(content=result.error)],
            "translated": "",
            "pronunciation_ko": "",
            "translation_direction": "",
            "last_asked_slot": "",
        }

    return {
        "messages": [AIMessage(content=result.reply)],
        "source_language": result.source_language,
        "translation_direction": result.direction,
        "translated": result.translated,
        "pronunciation_ko": result.pronunciation_ko,
        "last_asked_slot": "",
    }


def _route_after_resolve(state: TranslatorState) -> str:
    """resolve 후 다음 노드를 결정한다."""

    if state.get("conversation_ended"):
        return END
    if state.get("last_asked_slot") == "source_text":
        return "collect_source_text"
    if state.get("last_asked_slot") == "target_language":
        return "collect_target_language"
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
