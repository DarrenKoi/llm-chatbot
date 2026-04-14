"""LangGraph 기반 워크플로 오케스트레이터.

기존 orchestrator.py를 대체하며, 전체 흐름을 하나의 LangGraph StateGraph로 처리한다.
자식 워크플로(translator, chart_maker, travel_planner)는 서브그래프로 포함되어
handoff 스택 없이 interrupt/resume로 멀티턴 대화를 지원한다.
"""

import logging

from langgraph.types import Command

from api.cube.models import CubeIncomingMessage
from api.workflows.langgraph_checkpoint import build_thread_id, get_checkpointer
from api.workflows.models import WorkflowReply
from api.workflows.start_chat.lg_graph import build_lg_graph

log = logging.getLogger(__name__)

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        checkpointer = get_checkpointer()
        _compiled_graph = build_lg_graph().compile(checkpointer=checkpointer)
    return _compiled_graph


def handle_message(incoming: CubeIncomingMessage, attempt: int = 0) -> WorkflowReply:
    """Cube worker가 호출하는 LangGraph 워크플로 진입점."""

    del attempt

    graph = _get_graph()
    thread_id = build_thread_id(incoming.user_id, incoming.channel_id)
    config = {"configurable": {"thread_id": thread_id}}

    current = graph.get_state(config)

    if current.tasks:
        graph.invoke(Command(resume=incoming.message), config)
    else:
        graph.invoke(
            {
                "user_message": incoming.message,
                "user_id": incoming.user_id,
                "channel_id": incoming.channel_id,
            },
            config,
        )

    result_state = graph.get_state(config)

    if result_state.tasks:
        interrupt_value = result_state.tasks[0].interrupts[0].value
        reply = interrupt_value.get("reply", "") if isinstance(interrupt_value, dict) else str(interrupt_value)
    else:
        values = result_state.values
        messages = values.get("messages", [])
        reply = messages[-1].content if messages else ""

    workflow_id = result_state.values.get("active_workflow", "start_chat")

    return WorkflowReply(
        reply=reply or "[start_chat] 처리 완료.",
        workflow_id=workflow_id,
    )
