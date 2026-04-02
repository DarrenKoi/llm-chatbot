"""AT wafer quota 워크플로 전용 상태를 정의한다."""

from dataclasses import dataclass

from api.workflows.models import WorkflowState


@dataclass
class AtWaferQuotaWorkflowState(WorkflowState):
    """quota 조회와 후속 액션에 필요한 상태다."""

    quota_total: int = 0
    quota_remaining: int = 0
    requested_amount: int = 0
