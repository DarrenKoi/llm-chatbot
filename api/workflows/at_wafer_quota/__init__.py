"""AT wafer quota 워크플로 패키지."""

from __future__ import annotations


def get_workflow_definition() -> dict[str, object]:
    """at_wafer_quota 워크플로 정의를 반환한다."""

    from api.workflows.at_wafer_quota.graph import build_graph
    from api.workflows.at_wafer_quota.state import AtWaferQuotaWorkflowState

    return {
        "workflow_id": "at_wafer_quota",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": AtWaferQuotaWorkflowState,
        "handoff_keywords": ("wafer", "quota", "at wafer", "웨이퍼", "쿼터", "할당량"),
    }
