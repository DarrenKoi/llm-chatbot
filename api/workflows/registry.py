"""등록된 워크플로 그래프와 엔트리포인트를 조회한다."""

from collections.abc import Callable
from typing import Any

from api.workflows.at_wafer_quota.graph import build_graph as build_at_wafer_quota_graph
from api.workflows.chart_maker.graph import build_graph as build_chart_maker_graph
from api.workflows.common.graph import build_graph as build_common_graph
from api.workflows.start_chat.graph import build_graph as build_start_chat_graph
from api.workflows.ppt_maker.graph import build_graph as build_ppt_maker_graph
from api.workflows.recipe_requests.graph import build_graph as build_recipe_requests_graph
from api.workflows.sample.graph import build_graph as build_sample_graph

WorkflowDefinition = dict[str, Any]
WorkflowBuilder = Callable[[], WorkflowDefinition]

_WORKFLOWS: dict[str, WorkflowDefinition] = {
    "common": {
        "workflow_id": "common",
        "entry_node_id": "entry",
        "build_graph": build_common_graph,
    },
    "start_chat": {
        "workflow_id": "start_chat",
        "entry_node_id": "entry",
        "build_graph": build_start_chat_graph,
    },
    "chart_maker": {
        "workflow_id": "chart_maker",
        "entry_node_id": "entry",
        "build_graph": build_chart_maker_graph,
    },
    "ppt_maker": {
        "workflow_id": "ppt_maker",
        "entry_node_id": "entry",
        "build_graph": build_ppt_maker_graph,
    },
    "at_wafer_quota": {
        "workflow_id": "at_wafer_quota",
        "entry_node_id": "entry",
        "build_graph": build_at_wafer_quota_graph,
    },
    "recipe_requests": {
        "workflow_id": "recipe_requests",
        "entry_node_id": "entry",
        "build_graph": build_recipe_requests_graph,
    },
    "sample": {
        "workflow_id": "sample",
        "entry_node_id": "entry",
        "build_graph": build_sample_graph,
    },
}


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """등록된 workflow graph / entrypoint를 반환한다."""

    try:
        return _WORKFLOWS[workflow_id]
    except KeyError as exc:
        raise KeyError(f"등록되지 않은 workflow_id입니다: {workflow_id}") from exc
