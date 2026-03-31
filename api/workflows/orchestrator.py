"""Cube worker에서 호출하는 워크플로 진입점을 정의한다."""

from __future__ import annotations

from api.cube.models import CubeIncomingMessage
from api.workflows.models import WorkflowState
from api.workflows.registry import get_workflow
from api.workflows.state_service import load_state, save_state

DEFAULT_WORKFLOW_ID = "general_chat"
DEFAULT_ENTRY_NODE_ID = "entry"


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
        data={"latest_user_message": incoming.message},
    )
    workflow = get_workflow(state.workflow_id)
    workflow["build_graph"]()

    state.data["latest_user_message"] = incoming.message
    save_state(state)
    return f"[{workflow['workflow_id']}] 워크플로 스켈레톤이 준비되었습니다."
