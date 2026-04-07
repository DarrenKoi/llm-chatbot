"""워크플로 상태의 저장·조회·삭제 스텁을 제공한다."""

import json
from dataclasses import fields
from pathlib import Path

from api.config import WORKFLOW_STATE_DIR
from api.workflows.models import WorkflowState

_STATE_CLASSES: dict[str, type[WorkflowState]] = {}
_BASE_FIELD_NAMES = {field.name for field in fields(WorkflowState)}


def register_state_class(workflow_id: str, cls: type[WorkflowState]) -> None:
    """워크플로별 상태 클래스를 등록한다."""

    _STATE_CLASSES[workflow_id] = cls


def get_state_class(workflow_id: str) -> type[WorkflowState]:
    """workflow_id에 해당하는 상태 클래스를 반환한다."""

    if workflow_id in _STATE_CLASSES:
        return _STATE_CLASSES[workflow_id]

    try:
        from api.workflows.registry import get_workflow

        return get_workflow(workflow_id).get("state_cls", WorkflowState)
    except KeyError:
        return WorkflowState


def _serialize_state(state: WorkflowState) -> dict[str, object]:
    """상태 객체를 JSON 저장용 payload로 변환한다."""

    payload = dict(vars(state))
    payload["data"] = dict(getattr(state, "data", {}) or {})
    payload["stack"] = list(getattr(state, "stack", []) or [])

    for key, value in payload.items():
        if key not in _BASE_FIELD_NAMES:
            payload["data"].setdefault(key, value)

    return payload


def build_state(payload: dict[str, object]) -> WorkflowState:
    """저장 payload를 현재 workflow_id에 맞는 상태 객체로 복원한다."""

    workflow_id = str(payload.get("workflow_id", ""))
    cls = get_state_class(workflow_id)
    data = dict(payload.get("data", {}) or {})

    state_kwargs = {}
    for field in fields(cls):
        if field.name in payload:
            state_kwargs[field.name] = payload[field.name]
        elif field.name not in _BASE_FIELD_NAMES and field.name in data:
            state_kwargs[field.name] = data[field.name]

    return cls(**state_kwargs)


def _build_state_path(user_id: str, channel_id: str = "") -> Path:
    """사용자별 워크플로 상태 파일 경로를 생성한다."""

    safe_user_id = user_id.replace("/", "_")
    safe_channel_id = channel_id.replace("/", "_")
    if safe_channel_id:
        return WORKFLOW_STATE_DIR / f"{safe_user_id}__{safe_channel_id}.json"
    return WORKFLOW_STATE_DIR / f"{safe_user_id}.json"


def load_state(user_id: str, *, channel_id: str = "") -> WorkflowState | None:
    """사용자별 워크플로 상태를 조회한다."""

    state_path = _build_state_path(user_id, channel_id)
    if not state_path.exists() and channel_id:
        state_path = _build_state_path(user_id)
    if not state_path.exists():
        return None

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return build_state(payload)


def save_state(state: WorkflowState) -> WorkflowState:
    """워크플로 상태를 저장하고 동일 객체를 반환한다."""

    WORKFLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = _build_state_path(state.user_id, state.channel_id)
    state_path.write_text(
        json.dumps(_serialize_state(state), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return state


def clear_state(user_id: str, *, channel_id: str = "") -> None:
    """사용자별 워크플로 상태를 삭제한다."""

    state_path = _build_state_path(user_id, channel_id)
    if state_path.exists():
        state_path.unlink()
