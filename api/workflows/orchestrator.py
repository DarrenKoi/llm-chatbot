"""Cube worker에서 호출하는 워크플로 진입점을 정의한다."""

import logging

from api.cube.models import CubeIncomingMessage
from api.utils.logger import log_workflow_activity
from api.workflows.models import NodeResult, WorkflowState
from api.workflows.registry import get_workflow
from api.workflows.state_service import build_state, load_state, save_state

log = logging.getLogger(__name__)

DEFAULT_WORKFLOW_ID = "start_chat"
DEFAULT_ENTRY_NODE_ID = "entry"
MAX_RESUME_STEPS = 20


def _build_message_preview(message: str, *, limit: int = 120) -> str:
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 3]}..."


def _log_workflow_event(
    state: WorkflowState,
    event: str,
    *,
    level: int = logging.INFO,
    workflow_id: str | None = None,
    **data: object,
) -> None:
    target_workflow_id = workflow_id or state.workflow_id
    try:
        log_workflow_activity(
            target_workflow_id,
            event,
            state=state,
            level=level,
            **data,
        )
    except Exception:
        log.exception("워크플로 로그 기록에 실패했습니다: workflow=%s event=%s", target_workflow_id, event)


def _replace_state(target: WorkflowState, source: WorkflowState) -> WorkflowState:
    """기존 상태 객체를 새 payload로 동기화한다."""

    vars(target).clear()
    vars(target).update(vars(source))
    return target


def _coerce_state(
    state: WorkflowState,
    *,
    workflow_id: str | None = None,
    node_id: str | None = None,
    status: str | None = None,
    data: dict | None = None,
) -> WorkflowState:
    """현재 상태를 특정 워크플로 payload로 정규화한다."""

    payload = dict(vars(state))
    payload["workflow_id"] = workflow_id or state.workflow_id

    if node_id is not None:
        payload["node_id"] = node_id
    if status is not None:
        payload["status"] = status
    if data is not None:
        payload["data"] = data

    return build_state(payload)


def _reset_start_chat_state(user_id: str) -> WorkflowState:
    """새 사용자 턴을 위한 start_chat 상태를 재구성한다."""

    return build_state({
        "user_id": user_id,
        "workflow_id": DEFAULT_WORKFLOW_ID,
        "node_id": DEFAULT_ENTRY_NODE_ID,
        "status": "active",
        "data": {},
        "stack": [],
    })


def _restore_parent_workflow(state: WorkflowState) -> None:
    """자식 워크플로 종료 후 부모 워크플로 준비 상태로 복귀한다."""

    if not state.stack:
        return

    child_workflow_id = state.workflow_id
    return_point = state.stack.pop()
    parent_workflow_id = return_point["workflow_id"]

    if parent_workflow_id == DEFAULT_WORKFLOW_ID:
        restored_state = _reset_start_chat_state(state.user_id)
        restored_state.stack = list(state.stack)
    else:
        restored_state = _coerce_state(
            state,
            workflow_id=parent_workflow_id,
            node_id=return_point["node_id"],
            status="active",
        )

    _replace_state(state, restored_state)
    _log_workflow_event(
        state,
        "workflow_resumed_from_child",
        parent_workflow_id=parent_workflow_id,
        child_workflow_id=child_workflow_id,
        return_node_id=return_point["node_id"],
        stack_depth=len(state.stack),
    )


def _should_restore_parent(result: NodeResult) -> bool:
    """현재 결과가 handoff된 자식 워크플로의 종료 지점인지 판단한다."""

    if result.action == "complete":
        return True

    return result.action == "reply" and result.next_node_id in {None, "done"}


def _apply_result(state: WorkflowState, result: NodeResult) -> None:
    """NodeResult를 WorkflowState에 반영한다."""

    for key, value in result.data_updates.items():
        state.data[key] = value
        setattr(state, key, value)

    if result.next_node_id:
        state.node_id = result.next_node_id

    if result.action == "complete":
        state.status = "completed"
    elif result.action == "wait":
        state.status = "waiting_user_input"
    else:
        state.status = "active"


def _handle_handoff(state: WorkflowState, result: NodeResult, user_message: str) -> str:
    """현재 워크플로를 중단하고 대상 워크플로로 전환한다."""

    source_workflow_id = state.workflow_id
    source_node_id = state.node_id
    target_workflow_id = result.next_workflow_id
    if not target_workflow_id:
        log.warning("handoff 대상 워크플로가 지정되지 않았습니다.")
        _log_workflow_event(
            state,
            "workflow_handoff_missing_target",
            level=logging.WARNING,
            source_workflow_id=source_workflow_id,
        )
        return ""

    # 현재 위치를 스택에 저장 (복귀용)
    state.stack.append({
        "workflow_id": state.workflow_id,
        "node_id": state.node_id,
    })
    _log_workflow_event(
        state,
        "workflow_handoff_started",
        source_workflow_id=source_workflow_id,
        source_node_id=source_node_id,
        target_workflow_id=target_workflow_id,
        stack_depth=len(state.stack),
    )

    # 대상 워크플로로 전환
    target_def = get_workflow(target_workflow_id)
    target_state = _coerce_state(
        state,
        workflow_id=target_workflow_id,
        node_id=target_def["entry_node_id"],
        status="active",
    )
    _replace_state(state, target_state)
    _log_workflow_event(
        state,
        "workflow_handoff_entered",
        source_workflow_id=source_workflow_id,
        source_node_id=source_node_id,
        target_workflow_id=target_workflow_id,
    )

    # 대상 워크플로 그래프 실행
    target_graph = target_def["build_graph"]()
    reply = run_graph(target_graph, state, user_message)

    return reply


def run_graph(graph: dict, state: WorkflowState, user_message: str) -> str:
    """그래프 노드를 실행하고 최종 reply를 반환한다.

    action이 "resume"이면 다음 노드를 즉시 이어서 실행하고,
    "handoff"이면 대상 워크플로로 전환한다.
    그 외("reply", "wait", "complete" 등)에서는 멈춘다.
    """

    nodes = graph["nodes"]
    reply = ""
    last_result: NodeResult | None = None

    for step in range(MAX_RESUME_STEPS):
        node_fn = nodes.get(state.node_id)
        if node_fn is None:
            log.warning("노드를 찾을 수 없습니다: %s", state.node_id)
            _log_workflow_event(
                state,
                "workflow_node_missing",
                level=logging.WARNING,
                step=step,
                missing_node_id=state.node_id,
            )
            break

        current_node_id = state.node_id
        log.info(
            "[orchestrator] step=%d  node=%s  workflow=%s",
            step, state.node_id, state.workflow_id,
        )
        _log_workflow_event(
            state,
            "workflow_step_started",
            step=step,
            node_id=current_node_id,
        )

        try:
            result = node_fn(state, user_message)
        except Exception as exc:
            _log_workflow_event(
                state,
                "workflow_step_failed",
                level=logging.ERROR,
                step=step,
                node_id=current_node_id,
                error=str(exc),
            )
            raise
        last_result = result
        _apply_result(state, result)
        _log_workflow_event(
            state,
            "workflow_step_completed",
            step=step,
            node_id=current_node_id,
            action=result.action,
            next_node_id=result.next_node_id,
            next_workflow_id=result.next_workflow_id,
            reply_present=bool(result.reply),
            reply_length=len(result.reply),
            data_update_keys=sorted(result.data_updates),
            result_status=state.status,
        )

        if result.reply:
            reply = result.reply

        if result.action == "handoff":
            handoff_reply = _handle_handoff(state, result, user_message)
            if handoff_reply:
                reply = handoff_reply
            break

        if result.action != "resume":
            break
    else:
        log.warning("MAX_RESUME_STEPS(%d) 도달 — 루프를 중단합니다.", MAX_RESUME_STEPS)
        _log_workflow_event(
            state,
            "workflow_max_resume_steps_reached",
            level=logging.WARNING,
            max_resume_steps=MAX_RESUME_STEPS,
        )

    if last_result and state.stack and _should_restore_parent(last_result):
        _restore_parent_workflow(state)

    _log_workflow_event(
        state,
        "workflow_run_finished",
        reply_present=bool(reply),
        reply_length=len(reply),
        last_action=last_result.action if last_result else "",
        stack_depth=len(state.stack),
    )
    return reply


def handle_message(incoming: CubeIncomingMessage, attempt: int = 0) -> str:
    """
    Cube worker가 호출하는 workflow 진입점.
    active workflow를 이어서 실행하거나, 새 workflow를 시작한다.
    """

    del attempt

    loaded_state = load_state(incoming.user_id)
    if loaded_state is None:
        state = _reset_start_chat_state(incoming.user_id)
        _log_workflow_event(state, "workflow_state_initialized", reason="not_found")
    else:
        state = _coerce_state(loaded_state)
        _log_workflow_event(
            state,
            "workflow_state_loaded",
            loaded_workflow_id=loaded_state.workflow_id,
            loaded_node_id=loaded_state.node_id,
            loaded_status=loaded_state.status,
            stack_depth=len(getattr(loaded_state, "stack", []) or []),
        )
        if state.workflow_id == DEFAULT_WORKFLOW_ID and state.status == "completed":
            state = _reset_start_chat_state(incoming.user_id)
            _log_workflow_event(state, "workflow_state_reinitialized", reason="default_completed")

    state.data["latest_user_message"] = incoming.message
    _log_workflow_event(
        state,
        "workflow_message_received",
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        user_name=incoming.user_name,
        message_length=len(incoming.message),
        message_preview=_build_message_preview(incoming.message),
    )

    workflow_def = get_workflow(state.workflow_id)
    graph = workflow_def["build_graph"]()

    reply = run_graph(graph, state, incoming.message)

    save_state(state)
    _log_workflow_event(
        state,
        "workflow_state_saved",
        reply_present=bool(reply),
        reply_length=len(reply),
        state_data_keys=sorted(state.data),
        stack_depth=len(state.stack),
    )

    return reply or f"[{state.workflow_id}] 처리 완료."
