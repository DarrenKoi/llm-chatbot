"""__WORKFLOW_ID__ 워크플로 전용 상태를 정의한다."""

from dataclasses import dataclass

from api.workflows.models import WorkflowState


@dataclass
class __STATE_CLASS__(WorkflowState):
    """__WORKFLOW_ID__ 워크플로 상태.

    워크플로에 필요한 필드를 여기에 추가한다.
    예: destination: str = ""
    """
