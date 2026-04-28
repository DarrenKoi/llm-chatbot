"""로컬 개발용 LangGraph 워크플로 오케스트레이터."""

import importlib
import json
import logging
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from devtools.workflow_runner import conversation_history
from devtools.workflow_runner.identity import get_default_dev_user_id
from devtools.workflow_runner.registry import discover_workflows

log = logging.getLogger(__name__)

START_CHAT_ID = "start_chat"

_dev_workflows: dict[str, dict[str, object]] | None = None
_compiled_graphs: dict[str, Any] = {}
_checkpointers: dict[str, MemorySaver] = {}
_thread_generations: dict[tuple[str, str], int] = {}


def load_dev_workflows(*, force_reload: bool = False) -> dict[str, dict[str, object]]:
    """devtools/workflows 패키지에서 LangGraph 워크플로를 탐색한다."""

    global _dev_workflows

    if force_reload:
        _invalidate_dev_workflow_modules()
        _compiled_graphs.clear()
        _checkpointers.clear()
        _thread_generations.clear()
        _dev_workflows = None

    if _dev_workflows is None:
        _dev_workflows = discover_workflows(package_name="devtools.workflows")

    return _dev_workflows


def _invalidate_dev_workflow_modules() -> None:
    """이미 import된 devtools.workflows.* 모듈을 제거하여 재로드를 강제한다."""

    importlib.invalidate_caches()

    stale_keys = [
        key
        for key in sys.modules
        if (key.startswith("devtools.workflows.") or key.startswith("devtools.mcp_client."))
        and not key.endswith("__init__")
    ]
    for key in stale_keys:
        del sys.modules[key]

    pkg = sys.modules.get("devtools.workflows")
    if pkg is not None:
        importlib.reload(pkg)

    mcp_pkg = sys.modules.get("devtools.mcp_client")
    if mcp_pkg is not None:
        importlib.reload(mcp_pkg)


def list_dev_workflow_ids() -> list[str]:
    """등록된 dev workflow ID 목록을 반환한다.

    프로덕션 라우팅 테스트를 위해 start_chat을 맨 앞에 포함한다.
    """

    ids = sorted(load_dev_workflows().keys())
    ids.insert(0, START_CHAT_ID)
    return ids


def get_dev_workflow(workflow_id: str) -> dict[str, object]:
    """dev workflow 정의를 반환한다."""

    workflows = load_dev_workflows()
    try:
        return workflows[workflow_id]
    except KeyError as exc:
        raise KeyError(f"등록되지 않은 dev workflow입니다: {workflow_id}") from exc


def _get_compiled_graph(workflow_id: str):
    graph = _compiled_graphs.get(workflow_id)
    if graph is not None:
        return graph

    checkpointer = _checkpointers.setdefault(workflow_id, MemorySaver())

    if workflow_id == START_CHAT_ID:
        # 의도적인 cross-import 예외: dev runner UI에서 운영 start_chat 진입 라우팅을
        # 직접 검증하기 위해 운영 그래프를 lazy import한다. HARNESS.md "api/ ↔ devtools/
        # 격리 정책"의 일반 원칙에는 어긋나지만, "워크플로 entry 점검"이라는 이 단일
        # 용도가 dev 작업 자체의 일부라 유지한다. start_chat을 사용하지 않는 환경에서는
        # 이 import가 실행되지 않으므로 import-time 부작용은 없다.
        from api.workflows.start_chat.lg_graph import build_lg_graph

        graph = build_lg_graph().compile(checkpointer=checkpointer)
    else:
        workflow_def = get_dev_workflow(workflow_id)
        graph = workflow_def["build_lg_graph"]().compile(checkpointer=checkpointer)

    _compiled_graphs[workflow_id] = graph
    return graph


def _build_thread_id(workflow_id: str, user_id: str) -> str:
    generation = _thread_generations.get((workflow_id, user_id), 0)
    return f"devtools::{workflow_id}::{user_id}::{generation}"


def _build_config(workflow_id: str, user_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": _build_thread_id(workflow_id, user_id)}}


def handle_dev_message(
    workflow_id: str,
    user_message: str,
    user_id: str | None = None,
) -> dict[str, object]:
    """dev runner의 메시지 처리 진입점."""

    if workflow_id != START_CHAT_ID:
        get_dev_workflow(workflow_id)
    resolved_user_id = user_id or get_default_dev_user_id()

    graph = _get_compiled_graph(workflow_id)
    config = _build_config(workflow_id, resolved_user_id)
    before_state = graph.get_state(config)
    started_at = time.perf_counter()

    if before_state.tasks:
        graph.invoke(Command(resume=user_message), config)
        mode = "resume"
    else:
        graph.invoke(
            {
                "user_message": user_message,
                "user_id": resolved_user_id,
                "channel_id": workflow_id,
            },
            config,
        )
        mode = "invoke"

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    after_state = graph.get_state(config)
    final_reply = _extract_reply(after_state, fallback=f"[{workflow_id}] 처리 완료.")

    conversation_history.append_message(
        resolved_user_id,
        {"role": "user", "content": user_message},
        conversation_id=workflow_id,
    )
    conversation_history.append_message(
        resolved_user_id,
        {"role": "assistant", "content": final_reply},
        conversation_id=workflow_id,
    )

    return {
        "reply": final_reply,
        "state": _serialize_snapshot(after_state, workflow_id=workflow_id, user_id=resolved_user_id),
        "trace": [
            {
                "step": 0,
                "node_id": _detect_node_id(after_state, workflow_id),
                "action": _detect_action(before_state=before_state, after_state=after_state, mode=mode),
                "reply_preview": final_reply[:100],
                "elapsed_ms": elapsed_ms,
            }
        ],
    }


def get_dev_state(*, workflow_id: str, user_id: str | None = None) -> dict[str, object] | None:
    """현재 dev workflow state를 반환한다."""

    resolved_user_id = user_id or get_default_dev_user_id()
    graph = _compiled_graphs.get(workflow_id)
    if graph is None:
        return None

    snapshot = graph.get_state(_build_config(workflow_id, resolved_user_id))
    if not snapshot.values and not snapshot.tasks:
        return None

    return _serialize_snapshot(snapshot, workflow_id=workflow_id, user_id=resolved_user_id)


def reset_dev_state(*, workflow_id: str, user_id: str | None = None) -> None:
    """특정 workflow/user 조합의 dev state를 초기화한다."""

    resolved_user_id = user_id or get_default_dev_user_id()
    key = (workflow_id, resolved_user_id)
    _thread_generations[key] = _thread_generations.get(key, 0) + 1


def _extract_reply(snapshot, *, fallback: str) -> str:
    tasks = getattr(snapshot, "tasks", ())
    if tasks:
        first_task = tasks[0]
        interrupts = getattr(first_task, "interrupts", ())
        if interrupts:
            value = getattr(interrupts[0], "value", interrupts[0])
            if isinstance(value, dict):
                reply = value.get("reply", "")
                if reply:
                    return str(reply)
            return str(value)

    values = getattr(snapshot, "values", {}) or {}
    messages = values.get("messages", [])
    if messages:
        last_message = messages[-1]
        content = getattr(last_message, "content", "")
        if content:
            return str(content)

    pending_reply = values.get("pending_reply", "")
    if pending_reply:
        return str(pending_reply)

    return fallback


def _detect_action(*, before_state, after_state, mode: str) -> str:
    del before_state

    if getattr(after_state, "tasks", ()):
        return "interrupt"
    if mode == "resume":
        return "resume_complete"
    return "complete"


def _detect_node_id(snapshot, workflow_id: str) -> str:
    values = getattr(snapshot, "values", {}) or {}
    return str(values.get("active_workflow") or workflow_id)


def _serialize_snapshot(snapshot, *, workflow_id: str, user_id: str) -> dict[str, object]:
    return {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "thread_id": _build_thread_id(workflow_id, user_id),
        "waiting_for_input": bool(getattr(snapshot, "tasks", ())),
        "values": _json_safe(getattr(snapshot, "values", {})),
        "next": _json_safe(getattr(snapshot, "next", ())),
        "tasks": _serialize_tasks(getattr(snapshot, "tasks", ())),
    }


def _serialize_tasks(tasks: Sequence[Any]) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    for task in tasks:
        interrupts = []
        for interrupt in getattr(task, "interrupts", ()) or ():
            interrupts.append(_json_safe(getattr(interrupt, "value", interrupt)))
        serialized.append(
            {
                "name": str(getattr(task, "name", "")),
                "interrupts": interrupts,
            }
        )
    return serialized


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseMessage):
        return {
            "type": value.__class__.__name__,
            "content": value.content,
        }
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
