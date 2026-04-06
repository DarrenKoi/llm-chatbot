"""로컬 개발용 워크플로 오케스트레이터.

Production orchestrator의 run_graph()와 동일한 실행 루프를 사용하되,
각 step마다 trace 데이터를 수집하여 dev UI에서 확인할 수 있게 한다.
"""

import logging
import time
from dataclasses import asdict

from api.workflows.models import NodeResult, WorkflowState
from api.workflows.registry import discover_workflows
from api.workflows.state_service import (
    build_state,
    clear_state,
    load_state,
    register_state_class,
    save_state,
)

log = logging.getLogger(__name__)

MAX_RESUME_STEPS = 20
DEFAULT_USER_ID = "dev_user"

_dev_workflows: dict[str, dict] | None = None


def load_dev_workflows(*, force_reload: bool = False) -> dict[str, dict]:
    """devtools/workflows/ 패키지에서 워크플로를 탐색하고 state class를 등록한다."""

    global _dev_workflows

    if force_reload or _dev_workflows is None:
        _dev_workflows = discover_workflows(package_name="devtools.workflows")
        for workflow_id, definition in _dev_workflows.items():
            state_cls = definition.get("state_cls", WorkflowState)
            register_state_class(workflow_id, state_cls)
            log.info("dev workflow 등록: %s (state_cls=%s)", workflow_id, state_cls.__name__)

    return _dev_workflows


def list_dev_workflow_ids() -> list[str]:
    """등록된 dev workflow ID 목록을 반환한다."""

    return sorted(load_dev_workflows().keys())


def get_dev_workflow(workflow_id: str) -> dict:
    """dev workflow 정의를 반환한다."""

    workflows = load_dev_workflows()
    try:
        return workflows[workflow_id]
    except KeyError as exc:
        raise KeyError(f"등록되지 않은 dev workflow입니다: {workflow_id}") from exc


def run_graph_with_trace(
    graph: dict,
    state: WorkflowState,
    user_message: str,
) -> tuple[str, list[dict]]:
    """run_graph와 동일한 실행 루프 + step별 trace 수집.

    Returns:
        (reply, trace) 튜플. trace는 step별 실행 정보 리스트.
    """

    nodes = graph["nodes"]
    reply = ""
    trace: list[dict] = []

    for step in range(MAX_RESUME_STEPS):
        node_fn = nodes.get(state.node_id)
        if node_fn is None:
            log.warning("노드를 찾을 수 없습니다: %s", state.node_id)
            trace.append({
                "step": step,
                "node_id": state.node_id,
                "workflow_id": state.workflow_id,
                "error": f"노드를 찾을 수 없음: {state.node_id}",
            })
            break

        current_node_id = state.node_id
        start_time = time.perf_counter()

        try:
            result = node_fn(state, user_message)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            trace.append({
                "step": step,
                "node_id": current_node_id,
                "workflow_id": state.workflow_id,
                "error": str(exc),
                "elapsed_ms": elapsed_ms,
            })
            raise

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        _apply_result(state, result)

        trace.append({
            "step": step,
            "node_id": current_node_id,
            "workflow_id": state.workflow_id,
            "action": result.action,
            "reply_preview": result.reply[:100] if result.reply else "",
            "next_node_id": result.next_node_id,
            "data_updates": sorted(result.data_updates.keys()),
            "elapsed_ms": elapsed_ms,
            "state_snapshot": _serialize_state_safe(state),
        })

        if result.reply:
            reply = result.reply

        if result.action != "resume":
            break
    else:
        log.warning("MAX_RESUME_STEPS(%d) 도달", MAX_RESUME_STEPS)

    return reply, trace


def handle_dev_message(
    workflow_id: str,
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """dev runner의 메시지 처리 진입점.

    Returns:
        {"reply": str, "state": dict, "trace": list[dict]}
    """

    workflow_def = get_dev_workflow(workflow_id)

    loaded_state = load_state(user_id)
    if loaded_state is None or loaded_state.workflow_id != workflow_id:
        state = build_state({
            "user_id": user_id,
            "workflow_id": workflow_id,
            "node_id": workflow_def["entry_node_id"],
            "status": "active",
            "data": {},
            "stack": [],
        })
    else:
        state = loaded_state

    state.data["latest_user_message"] = user_message

    graph = workflow_def["build_graph"]()
    reply, trace = run_graph_with_trace(graph, state, user_message)

    save_state(state)

    return {
        "reply": reply or f"[{workflow_id}] 처리 완료.",
        "state": _serialize_state_safe(state),
        "trace": trace,
    }


def get_dev_state(user_id: str = DEFAULT_USER_ID) -> dict | None:
    """현재 dev workflow state를 반환한다."""

    state = load_state(user_id)
    if state is None:
        return None
    return _serialize_state_safe(state)


def reset_dev_state(user_id: str = DEFAULT_USER_ID) -> None:
    """dev workflow state를 초기화한다."""

    clear_state(user_id)


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


def _serialize_state_safe(state: WorkflowState) -> dict:
    """상태를 JSON 직렬화 가능한 dict로 변환한다."""

    try:
        return asdict(state)
    except Exception:
        return dict(vars(state))
