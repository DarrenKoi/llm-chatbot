"""__WORKFLOW_ID__ 워크플로 전용 LangGraph 상태를 정의한다."""

from devtools.workflows.lg_state import ChatState


class __STATE_CLASS__(ChatState, total=False):
    """__WORKFLOW_ID__ 워크플로 상태.

    워크플로에 필요한 필드를 여기에 추가한다.
    예: destination: str
    """
