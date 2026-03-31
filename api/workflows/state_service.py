"""워크플로 상태의 저장·조회·삭제 스텁을 제공한다."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from api.config import WORKFLOW_STATE_DIR
from api.workflows.models import WorkflowState

_STATE_CLASSES: dict[str, type[WorkflowState]] = {}


def register_state_class(workflow_id: str, cls: type[WorkflowState]) -> None:
    """워크플로별 상태 클래스를 등록한다."""

    _STATE_CLASSES[workflow_id] = cls


def _build_state_path(user_id: str) -> Path:
    """사용자별 워크플로 상태 파일 경로를 생성한다."""

    safe_user_id = user_id.replace("/", "_")
    return WORKFLOW_STATE_DIR / f"{safe_user_id}.json"


def load_state(user_id: str) -> WorkflowState | None:
    """사용자별 워크플로 상태를 조회한다."""

    state_path = _build_state_path(user_id)
    if not state_path.exists():
        return None

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    cls = _STATE_CLASSES.get(payload.get("workflow_id", ""), WorkflowState)
    return cls(**payload)


def save_state(state: WorkflowState) -> WorkflowState:
    """워크플로 상태를 저장하고 동일 객체를 반환한다."""

    WORKFLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = _build_state_path(state.user_id)
    state_path.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return state


def clear_state(user_id: str) -> None:
    """사용자별 워크플로 상태를 삭제한다."""

    state_path = _build_state_path(user_id)
    if state_path.exists():
        state_path.unlink()
