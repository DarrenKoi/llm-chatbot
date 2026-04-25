"""LangGraph 기반 워크플로 오케스트레이터.

기존 orchestrator.py를 대체하며, 전체 흐름을 하나의 LangGraph StateGraph로 처리한다.
자식 워크플로(translator)는 서브그래프로 포함되어
handoff 스택 없이 interrupt/resume로 멀티턴 대화를 지원한다.
"""

import logging
from typing import Any

from langgraph.types import Command

from api.cube.models import CubeIncomingMessage
from api.logging_service import log_workflow_activity
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


def _snapshot_values(snapshot: Any) -> dict[str, Any]:
    values = getattr(snapshot, "values", None)
    if isinstance(values, dict):
        return values
    return {}


def _normalize_node_id(value: Any) -> str | None:
    if isinstance(value, (tuple, list)):
        if not value:
            return None
        return _normalize_node_id(value[-1])
    if value is None:
        return None
    node_id = str(value).strip()
    return node_id or None


def _snapshot_workflow_id(snapshot: Any) -> str:
    workflow_id = _snapshot_values(snapshot).get("active_workflow")
    if workflow_id:
        return str(workflow_id)
    return "start_chat"


def _snapshot_node_id(snapshot: Any) -> str | None:
    next_nodes = getattr(snapshot, "next", ())
    if isinstance(next_nodes, (tuple, list)) and next_nodes:
        node_id = _normalize_node_id(next_nodes[0])
        if node_id:
            return node_id

    tasks = getattr(snapshot, "tasks", ())
    if tasks:
        task = tasks[0]
        for attribute in ("name", "node", "path"):
            node_id = _normalize_node_id(getattr(task, attribute, None))
            if node_id:
                return node_id

    return None


def _snapshot_waiting_for(snapshot: Any) -> str | None:
    waiting_for = _snapshot_values(snapshot).get("last_asked_slot")
    if waiting_for is None:
        return None
    value = str(waiting_for).strip()
    return value or None


def _status_before_run(snapshot: Any) -> str:
    if getattr(snapshot, "tasks", ()):
        return "waiting_user_input"
    return "active"


def _status_after_run(snapshot: Any) -> str:
    values = _snapshot_values(snapshot)
    if getattr(snapshot, "tasks", ()):
        return "waiting_user_input"
    if values.get("conversation_ended"):
        return "cancelled"
    return "completed"


def _user_state(snapshot: Any, *, after_run: bool) -> str:
    waiting_for = _snapshot_waiting_for(snapshot)
    if getattr(snapshot, "tasks", ()):
        if waiting_for:
            return f"waiting_for_{waiting_for}"
        return "waiting_user_input"

    values = _snapshot_values(snapshot)
    if values.get("conversation_ended"):
        return "conversation_ended"

    node_id = _snapshot_node_id(snapshot)
    if node_id:
        return node_id

    return _snapshot_workflow_id(snapshot) if after_run else "active"


def _log_workflow_snapshot(
    *,
    event: str,
    snapshot: Any,
    incoming: CubeIncomingMessage,
    status: str,
    resumed_from_interrupt: bool,
    previous_workflow_id: str | None = None,
    reply_length: int | None = None,
    error: str | None = None,
) -> None:
    workflow_id = _snapshot_workflow_id(snapshot)
    payload: dict[str, Any] = {
        "channel_id": incoming.channel_id,
        "message_id": incoming.message_id,
        "message_length": len(incoming.message),
        "active_workflow": workflow_id,
        "user_state": _user_state(snapshot, after_run=event != "workflow_message_received"),
        "resumed_from_interrupt": resumed_from_interrupt,
        "conversation_ended": bool(_snapshot_values(snapshot).get("conversation_ended")),
    }

    node_id = _snapshot_node_id(snapshot)
    waiting_for = _snapshot_waiting_for(snapshot)
    next_nodes = getattr(snapshot, "next", ())

    if waiting_for is not None:
        payload["waiting_for"] = waiting_for
    if isinstance(next_nodes, (tuple, list)) and next_nodes:
        payload["next_nodes"] = [str(node) for node in next_nodes]
    if previous_workflow_id is not None and previous_workflow_id != workflow_id:
        payload["previous_workflow_id"] = previous_workflow_id
    if reply_length is not None:
        payload["reply_length"] = reply_length
    if error is not None:
        payload["error"] = error

    log_workflow_activity(
        workflow_id,
        event,
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        node_id=node_id,
        status=status,
        **payload,
    )


def handle_message(incoming: CubeIncomingMessage, attempt: int = 0) -> WorkflowReply:
    """Cube worker가 호출하는 LangGraph 워크플로 진입점."""

    del attempt

    graph = _get_graph()
    thread_id = build_thread_id(incoming.user_id, incoming.channel_id)
    config = {"configurable": {"thread_id": thread_id}}

    current = graph.get_state(config)
    resumed_from_interrupt = bool(current.tasks)
    _log_workflow_snapshot(
        event="workflow_message_received",
        snapshot=current,
        incoming=incoming,
        status=_status_before_run(current),
        resumed_from_interrupt=resumed_from_interrupt,
    )

    try:
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
    except Exception as exc:
        _log_workflow_snapshot(
            event="workflow_message_failed",
            snapshot=current,
            incoming=incoming,
            status="failed",
            resumed_from_interrupt=resumed_from_interrupt,
            error=str(exc),
        )
        raise

    result_state = graph.get_state(config)

    if result_state.tasks:
        interrupt_value = result_state.tasks[0].interrupts[0].value
        reply = interrupt_value.get("reply", "") if isinstance(interrupt_value, dict) else str(interrupt_value)
    else:
        values = result_state.values
        messages = values.get("messages", [])
        reply = messages[-1].content if messages else ""

    workflow_id = result_state.values.get("active_workflow", "start_chat")
    _log_workflow_snapshot(
        event="workflow_message_processed",
        snapshot=result_state,
        incoming=incoming,
        status=_status_after_run(result_state),
        resumed_from_interrupt=resumed_from_interrupt,
        previous_workflow_id=_snapshot_workflow_id(current),
        reply_length=len(reply or ""),
    )

    return WorkflowReply(
        reply=reply or "[start_chat] 처리 완료.",
        workflow_id=workflow_id,
    )
