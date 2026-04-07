"""차트 생성 LangGraph 어댑터.

LangGraph 그래프를 기존 오케스트레이터의 ``build_graph() -> dict`` 인터페이스로
래핑한다.
"""

import logging

from langgraph.types import Command

from api.workflows.chart_maker.lg_graph import build_lg_graph
from api.workflows.chart_maker.state import ChartMakerWorkflowState
from api.workflows.langgraph_checkpoint import build_thread_id, get_checkpointer
from api.workflows.models import NodeResult

log = logging.getLogger(__name__)

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        # 루트 lg_orchestrator와 체크포인트 컬렉션을 공유하지 않도록
        # 호환용 어댑터는 MemorySaver만 사용한다.
        checkpointer = get_checkpointer(persistent=False)
        _compiled_graph = build_lg_graph().compile(checkpointer=checkpointer)
    return _compiled_graph


def _run_lg_node(state: ChartMakerWorkflowState, user_message: str) -> NodeResult:
    """LangGraph 그래프를 실행하거나 중단된 상태에서 재개한다."""

    graph = _get_graph()
    thread_id = build_thread_id(state.user_id, getattr(state, "channel_id", ""))
    config = {"configurable": {"thread_id": thread_id}}

    current = graph.get_state(config)

    if current.tasks:
        graph.invoke(Command(resume=user_message), config)
    else:
        lg_state = {
            "user_message": user_message,
            "user_id": state.user_id,
            "channel_id": getattr(state, "channel_id", ""),
            "workflow_id": "chart_maker",
        }
        graph.invoke(lg_state, config)

    result_state = graph.get_state(config)

    if result_state.tasks:
        interrupt_value = result_state.tasks[0].interrupts[0].value
        reply = interrupt_value.get("reply", "") if isinstance(interrupt_value, dict) else str(interrupt_value)

        values = result_state.values
        return NodeResult(
            action="wait",
            reply=reply,
            next_node_id="entry",
            data_updates={
                "chart_type": values.get("chart_type", ""),
            },
        )

    values = result_state.values
    messages = values.get("messages", [])
    reply = messages[-1].content if messages else ""

    return NodeResult(
        action="reply",
        reply=reply,
        next_node_id="done",
        data_updates={
            "chart_type": values.get("chart_type", ""),
            "chart_spec": values.get("chart_spec", {}),
        },
    )


def build_graph() -> dict:
    """기존 오케스트레이터용 그래프 정의를 반환한다."""

    return {
        "workflow_id": "chart_maker",
        "entry_node_id": "entry",
        "nodes": {
            "entry": _run_lg_node,
            "collect_requirements": _run_lg_node,
            "build_spec": _run_lg_node,
        },
    }
