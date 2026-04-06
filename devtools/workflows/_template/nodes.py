"""__WORKFLOW_ID__ 워크플로 노드 함수."""

from api.workflows.models import NodeResult

from .state import __STATE_CLASS__


def entry_node(state: __STATE_CLASS__, user_message: str) -> NodeResult:
    """워크플로 진입 노드.

    사용자 메시지를 받아 첫 응답을 반환한다.
    """

    return NodeResult(
        action="reply",
        reply=f"[__WORKFLOW_ID__] 메시지를 받았습니다: {user_message}",
    )
