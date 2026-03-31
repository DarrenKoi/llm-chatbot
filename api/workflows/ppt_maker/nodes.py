"""프레젠테이션 생성 워크플로 노드 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.models import NodeResult
from api.workflows.ppt_maker.state import PptMakerWorkflowState


def entry_node(state: PptMakerWorkflowState, user_message: str) -> NodeResult:
    """프레젠테이션 생성 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="collect_brief")


def collect_brief_node(state: PptMakerWorkflowState, user_message: str) -> NodeResult:
    """발표 목적과 청중을 수집하는 노드 스텁이다."""

    del state
    return NodeResult(
        action="wait",
        next_node_id="draft_outline",
        data_updates={"audience": user_message.strip()},
    )


def draft_outline_node(state: PptMakerWorkflowState, user_message: str) -> NodeResult:
    """개요 초안 생성 노드 스텁이다."""

    del user_message
    outline = state.outline or ["소개", "핵심 메시지", "다음 단계"]
    return NodeResult(
        action="reply",
        reply="PPT 아웃라인 스켈레톤입니다.",
        next_node_id="done",
        data_updates={"outline": outline},
    )
