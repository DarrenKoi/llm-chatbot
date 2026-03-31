"""레시피 요청 워크플로 노드 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.models import NodeResult
from api.workflows.recipe_requests.state import RecipeRequestsWorkflowState


def entry_node(state: RecipeRequestsWorkflowState, user_message: str) -> NodeResult:
    """레시피 요청 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="collect_slots")


def collect_slots_node(state: RecipeRequestsWorkflowState, user_message: str) -> NodeResult:
    """필수 입력 수집 노드 스텁이다."""

    del state
    return NodeResult(
        action="wait",
        next_node_id="confirm_request",
        data_updates={"recipe_type": user_message.strip()},
    )


def confirm_request_node(state: RecipeRequestsWorkflowState, user_message: str) -> NodeResult:
    """입력 요약 및 확인 노드 스텁이다."""

    del user_message
    reply = f"레시피 요청 스켈레톤 요약: {state.recipe_type or '미정'}"
    return NodeResult(action="reply", reply=reply, next_node_id="done")
