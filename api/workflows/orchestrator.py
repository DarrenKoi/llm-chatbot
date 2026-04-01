"""Cube worker에서 호출하는 워크플로 진입점을 정의한다."""

import logging

from api.cube.models import CubeIncomingMessage
from api.workflows.models import NodeResult, WorkflowState
from api.workflows.registry import get_workflow
from api.workflows.state_service import load_state, save_state

log = logging.getLogger(__name__)

DEFAULT_WORKFLOW_ID = "start_chat"
DEFAULT_ENTRY_NODE_ID = "entry"
MAX_RESUME_STEPS = 20


def _apply_result(state: WorkflowState, result: NodeResult) -> None:
    """NodeResult를 WorkflowState에 반영한다."""

    state.data.update(result.data_updates)

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

    target_workflow_id = result.next_workflow_id
    if not target_workflow_id:
        log.warning("handoff 대상 워크플로가 지정되지 않았습니다.")
        return ""

    # 현재 위치를 스택에 저장 (복귀용)
    state.stack.append({
        "workflow_id": state.workflow_id,
        "node_id": state.node_id,
    })

    # 대상 워크플로로 전환
    target_def = get_workflow(target_workflow_id)
    state.workflow_id = target_workflow_id
    state.node_id = target_def["entry_node_id"]
    state.status = "active"

    # 대상 워크플로 그래프 실행
    target_graph = target_def["build_graph"]()
    reply = run_graph(target_graph, state, user_message)

    # 대상 워크플로가 완료되면 스택에서 복귀
    if state.status == "completed" and state.stack:
        return_point = state.stack.pop()
        state.workflow_id = return_point["workflow_id"]
        state.node_id = return_point["node_id"]
        state.status = "active"

    return reply


def run_graph(graph: dict, state: WorkflowState, user_message: str) -> str:
    """그래프 노드를 실행하고 최종 reply를 반환한다.

    action이 "resume"이면 다음 노드를 즉시 이어서 실행하고,
    "handoff"이면 대상 워크플로로 전환한다.
    그 외("reply", "wait", "complete" 등)에서는 멈춘다.
    """

    nodes = graph["nodes"]
    reply = ""

    for step in range(MAX_RESUME_STEPS):
        node_fn = nodes.get(state.node_id)
        if node_fn is None:
            log.warning("노드를 찾을 수 없습니다: %s", state.node_id)
            break

        log.info(
            "[orchestrator] step=%d  node=%s  workflow=%s",
            step, state.node_id, state.workflow_id,
        )

        result: NodeResult = node_fn(state, user_message)
        _apply_result(state, result)

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

    return reply


def handle_message(incoming: CubeIncomingMessage, attempt: int = 0) -> str:
    """
    Cube worker가 호출하는 workflow 진입점.
    active workflow를 이어서 실행하거나, 새 workflow를 시작한다.
    """

    del attempt

    state = load_state(incoming.user_id) or WorkflowState(
        user_id=incoming.user_id,
        workflow_id=DEFAULT_WORKFLOW_ID,
        node_id=DEFAULT_ENTRY_NODE_ID,
        data={},
    )
    state.data["latest_user_message"] = incoming.message

    workflow_def = get_workflow(state.workflow_id)
    graph = workflow_def["build_graph"]()

    reply = run_graph(graph, state, incoming.message)

    save_state(state)

    return reply or f"[{state.workflow_id}] 처리 완료."
