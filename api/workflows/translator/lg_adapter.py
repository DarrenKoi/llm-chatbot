"""번역 서비스 LangGraph 어댑터.

LangGraph 그래프를 기존 오케스트레이터의 ``build_graph() -> dict`` 인터페이스로
래핑한다. 오케스트레이터가 어떤 노드 ID를 호출하든 내부적으로 LangGraph 그래프를
invoke/resume 한다.
"""

import logging

from langgraph.types import Command

from api.workflows.langgraph_checkpoint import build_thread_id, get_checkpointer
from api.workflows.models import NodeResult
from api.workflows.translator.lg_graph import build_lg_graph
from api.workflows.translator.state import TranslatorWorkflowState
from api.workflows.translator.tools import register_translator_tools

log = logging.getLogger(__name__)

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        # 루트 lg_orchestrator만 MongoDB 체크포인터를 사용한다.
        # 호환용 어댑터는 프로세스 로컬 MemorySaver로만 상태를 유지해
        # 별도 그래프 스키마가 동일한 체크포인트 컬렉션을 공유하지 않도록 한다.
        checkpointer = get_checkpointer(persistent=False)
        builder = build_lg_graph()
        _compiled_graph = builder.compile(checkpointer=checkpointer)
    return _compiled_graph


def _run_lg_node(state: TranslatorWorkflowState, user_message: str) -> NodeResult:
    """LangGraph 그래프를 실행하거나 중단된 상태에서 재개한다."""

    graph = _get_graph()
    thread_id = build_thread_id(state.user_id, getattr(state, "channel_id", ""))
    config = {"configurable": {"thread_id": thread_id}}

    current = graph.get_state(config)

    if current.tasks:
        graph.invoke(Command(resume=user_message), config)
    else:
        lg_state = {
            "user_message": user_message,
            "user_id": state.user_id,
            "channel_id": getattr(state, "channel_id", ""),
            "workflow_id": "translator",
            "source_text": getattr(state, "source_text", ""),
            "target_language": getattr(state, "target_language", ""),
            "last_asked_slot": getattr(state, "last_asked_slot", ""),
        }
        graph.invoke(lg_state, config)

    result_state = graph.get_state(config)

    if result_state.tasks:
        interrupt_value = result_state.tasks[0].interrupts[0].value
        reply = interrupt_value.get("reply", "") if isinstance(interrupt_value, dict) else str(interrupt_value)

        values = result_state.values
        return NodeResult(
            action="wait",
            reply=reply,
            next_node_id="entry",
            data_updates={
                "source_text": values.get("source_text", ""),
                "target_language": values.get("target_language", ""),
                "last_asked_slot": values.get("last_asked_slot", ""),
            },
        )

    values = result_state.values
    messages = values.get("messages", [])
    reply = messages[-1].content if messages else ""

    return NodeResult(
        action="complete",
        reply=reply,
        next_node_id="entry",
        data_updates={
            "source_text": values.get("source_text", ""),
            "source_language": values.get("source_language", ""),
            "target_language": values.get("target_language", ""),
            "translated": values.get("translated", ""),
            "pronunciation_ko": values.get("pronunciation_ko", ""),
            "translation_direction": values.get("translation_direction", ""),
            "last_asked_slot": "",
        },
    )


def build_graph() -> dict:
    """기존 오케스트레이터용 그래프 정의를 반환한다.

    모든 노드 ID가 동일한 ``_run_lg_node``를 가리킨다. LangGraph가
    내부적으로 노드 라우팅을 관리하므로 오케스트레이터의 node_id와
    무관하게 올바른 노드가 실행된다.
    """

    register_translator_tools()

    return {
        "workflow_id": "translator",
        "entry_node_id": "entry",
        "nodes": {
            "entry": _run_lg_node,
            "collect_source_text": _run_lg_node,
            "collect_target_language": _run_lg_node,
            "translate": _run_lg_node,
        },
    }
