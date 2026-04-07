"""로컬 개발용 워크플로 오케스트레이터.

Production orchestrator의 run_graph()와 동일한 실행 루프를 사용하되,
각 step마다 trace 데이터를 수집하여 dev UI에서 확인할 수 있게 한다.
"""

import importlib
import json
import logging
import sys
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
from devtools.workflow_runner.identity import get_default_dev_user_id

log = logging.getLogger(__name__)

MAX_RESUME_STEPS = 20

_dev_workflows: dict[str, dict] | None = None


def load_dev_workflows(*, force_reload: bool = False) -> dict[str, dict]:
    """devtools/workflows/ 패키지에서 워크플로를 탐색하고 state class를 등록한다."""

    global _dev_workflows

    if force_reload or _dev_workflows is None:
        if force_reload:
            _invalidate_dev_workflow_modules()

        _dev_workflows = discover_workflows(package_name="devtools.workflows")
        for workflow_id, definition in _dev_workflows.items():
            state_cls = definition.get("state_cls", WorkflowState)
            register_state_class(workflow_id, state_cls)
            log.info("dev workflow 등록: %s (state_cls=%s)", workflow_id, state_cls.__name__)

    return _dev_workflows


def _invalidate_dev_workflow_modules() -> None:
    """이미 import된 devtools.workflows.* 모듈을 제거하여 재로드를 강제한다."""

    importlib.invalidate_caches()

    stale_keys = [
        key
        for key in sys.modules
        if (key.startswith("devtools.workflows.") or key.startswith("devtools.mcp.")) and not key.endswith("__init__")
    ]
    for key in stale_keys:
        del sys.modules[key]

    # devtools.workflows 패키지 자체도 재로드
    pkg = sys.modules.get("devtools.workflows")
    if pkg is not None:
        importlib.reload(pkg)

    mcp_pkg = sys.modules.get("devtools.mcp")
    if mcp_pkg is not None:
        importlib.reload(mcp_pkg)


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

    Production의 handoff/parent-restore 로직도 포함하여
    로컬에서 다중 워크플로 구성을 정확히 검증할 수 있다.

    Returns:
        (reply, trace) 튜플. trace는 step별 실행 정보 리스트.
    """

    nodes = graph["nodes"]
    reply = ""
    trace: list[dict] = []
    last_result: NodeResult | None = None

    for step in range(MAX_RESUME_STEPS):
        node_fn = nodes.get(state.node_id)
        if node_fn is None:
            log.warning("노드를 찾을 수 없습니다: %s", state.node_id)
            trace.append(
                {
                    "step": step,
                    "node_id": state.node_id,
                    "workflow_id": state.workflow_id,
                    "error": f"노드를 찾을 수 없음: {state.node_id}",
                }
            )
            break

        current_node_id = state.node_id
        start_time = time.perf_counter()

        try:
            result = node_fn(state, user_message)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            trace.append(
                {
                    "step": step,
                    "node_id": current_node_id,
                    "workflow_id": state.workflow_id,
                    "error": str(exc),
                    "elapsed_ms": elapsed_ms,
                }
            )
            raise

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        last_result = result
        _apply_result(state, result)

        trace.append(
            {
                "step": step,
                "node_id": current_node_id,
                "workflow_id": state.workflow_id,
                "action": result.action,
                "reply_preview": result.reply[:100] if result.reply else "",
                "next_node_id": result.next_node_id,
                "next_workflow_id": result.next_workflow_id,
                "data_updates": sorted(result.data_updates.keys()),
                "elapsed_ms": elapsed_ms,
                "state_snapshot": _serialize_state_safe(state),
            }
        )

        if result.reply:
            reply = result.reply

        # handoff: 대상 워크플로로 전환 후 그 그래프를 이어서 실행
        if result.action == "handoff":
            handoff_reply, handoff_trace = _handle_handoff(state, result, user_message)
            trace.extend(handoff_trace)
            if handoff_reply:
                reply = handoff_reply
            break

        if result.action != "resume":
            break
    else:
        log.warning("MAX_RESUME_STEPS(%d) 도달", MAX_RESUME_STEPS)

    # Production과 동일하게 parent workflow 복원
    if last_result and state.stack and _should_restore_parent(last_result):
        _restore_parent_workflow(state)

    return reply, trace


def _handle_handoff(
    state: WorkflowState,
    result: NodeResult,
    user_message: str,
) -> tuple[str, list[dict]]:
    """현재 워크플로를 중단하고 대상 워크플로로 전환한다."""

    target_workflow_id = result.next_workflow_id
    if not target_workflow_id:
        log.warning("handoff 대상 워크플로가 지정되지 않았습니다.")
        return "", []

    # 현재 위치를 스택에 저장 (복귀용)
    state.stack.append(
        {
            "workflow_id": state.workflow_id,
            "node_id": state.node_id,
        }
    )

    # 대상 워크플로 로드 (dev workflows에서 먼저, 없으면 production에서)
    try:
        target_def = get_dev_workflow(target_workflow_id)
    except KeyError:
        from api.workflows.registry import get_workflow

        target_def = get_workflow(target_workflow_id)

    # 대상 워크플로로 전환
    state.workflow_id = target_workflow_id
    state.node_id = target_def["entry_node_id"]
    state.status = "active"

    target_graph = target_def["build_graph"]()
    return run_graph_with_trace(target_graph, state, user_message)


def _should_restore_parent(result: NodeResult) -> bool:
    """현재 결과가 handoff된 자식 워크플로의 종료 지점인지 판단한다."""

    if result.action == "complete":
        return True
    return result.action == "reply" and result.next_node_id in {None, "done"}


def _restore_parent_workflow(state: WorkflowState) -> None:
    """자식 워크플로 종료 후 부모 워크플로 준비 상태로 복귀한다."""

    if not state.stack:
        return

    return_point = state.stack.pop()
    state.workflow_id = return_point["workflow_id"]
    state.node_id = return_point["node_id"]
    state.status = "active"


def handle_dev_message(
    workflow_id: str,
    user_message: str,
    user_id: str | None = None,
) -> dict:
    """dev runner의 메시지 처리 진입점.

    Returns:
        {"reply": str, "state": dict, "trace": list[dict]}
    """

    workflow_def = get_dev_workflow(workflow_id)
    resolved_user_id = user_id or get_default_dev_user_id()

    loaded_state = load_state(resolved_user_id)
    if loaded_state is None or loaded_state.workflow_id != workflow_id:
        state = build_state(
            {
                "user_id": resolved_user_id,
                "workflow_id": workflow_id,
                "node_id": workflow_def["entry_node_id"],
                "status": "active",
                "data": {},
                "stack": [],
            }
        )
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


def get_dev_state(user_id: str | None = None) -> dict | None:
    """현재 dev workflow state를 반환한다."""

    resolved_user_id = user_id or get_default_dev_user_id()
    state = load_state(resolved_user_id)
    if state is None:
        return None
    return _serialize_state_safe(state)


def reset_dev_state(user_id: str | None = None) -> None:
    """dev workflow state를 초기화한다."""

    clear_state(user_id or get_default_dev_user_id())


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
    """상태를 JSON 직렬화 가능한 dict로 변환한다.

    Path, datetime 등 비원시 타입이 있을 수 있으므로 default=str로 처리한다.
    """

    try:
        raw = asdict(state)
    except Exception:
        raw = dict(vars(state))

    return json.loads(json.dumps(raw, default=str))
