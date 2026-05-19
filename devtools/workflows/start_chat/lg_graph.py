"""dev runner 전용 start_chat LangGraph.

운영 api/workflows/start_chat/lg_graph.py의 라우팅 부분만 미러링한 가벼운 사본이다.
목적은 promote 전 신규 핸드오프 워크플로의 키워드 매칭/라우팅 검증.
RAG/file/profile/LLM 노드는 의도적으로 미러링하지 않으며, 매칭 실패 시 noop_reply가
응답 자리를 표시만 한다.
"""

import logging

from langgraph.graph import END, StateGraph

from devtools.workflows.start_chat.lg_state import DevStartChatState

log = logging.getLogger(__name__)

_NOOP_REPLY_TEXT = "[dev] 핸드오프 매칭 실패 — 운영에서는 RAG/LLM generate_reply로 갔을 자리입니다."


def _get_handoff_subgraph_builders() -> dict[str, object]:
    """devtools 레지스트리에서 handoff 워크플로의 그래프 빌더를 수집한다."""

    from devtools.workflow_runner.dev_orchestrator import load_dev_workflows
    from devtools.workflow_runner.registry import list_handoff_workflows

    builders: dict[str, object] = {}
    for workflow_def in list_handoff_workflows(load_dev_workflows()):
        workflow_id = workflow_def["workflow_id"]
        builder = workflow_def.get("build_lg_graph")
        if callable(builder):
            builders[workflow_id] = builder
    return builders


def entry_node(state: DevStartChatState) -> dict:
    """dev에서는 진입 시 별도 처리가 없다 (운영의 프로필 로딩은 미러링하지 않음)."""

    del state
    return {}


def classify_node(state: DevStartChatState) -> dict:
    """사용자 메시지를 devtools 핸드오프 키워드와 매칭한다."""

    from devtools.workflow_runner.dev_orchestrator import load_dev_workflows
    from devtools.workflow_runner.registry import list_handoff_workflows

    user_message = state.get("user_message", "").strip().lower()
    if not user_message:
        return {"active_workflow": "start_chat", "handoff_match_reason": ""}

    for workflow_def in list_handoff_workflows(load_dev_workflows()):
        workflow_id = workflow_def["workflow_id"]
        for keyword in workflow_def.get("handoff_keywords", ()):
            if keyword in user_message:
                return {"active_workflow": workflow_id, "handoff_match_reason": keyword}

    return {"active_workflow": "start_chat", "handoff_match_reason": ""}


def noop_reply_node(state: DevStartChatState) -> dict:
    """매칭 실패 시 호출 — dev에서는 LLM을 부르지 않고 자리표시만 응답한다."""

    del state
    return {"pending_reply": _NOOP_REPLY_TEXT}


def _route_after_classify(state: DevStartChatState) -> str:
    intent = state.get("active_workflow", "start_chat")
    if intent in _get_handoff_subgraph_builders():
        return intent
    return "noop_reply"


def build_lg_graph() -> StateGraph:
    """dev start_chat LangGraph StateGraph 빌더를 반환한다.

    devtools 레지스트리의 handoff 워크플로 각각을 서브그래프로 포함한다.
    """

    handoff_subgraphs = _get_handoff_subgraph_builders()
    builder = StateGraph(DevStartChatState)

    builder.add_node("entry", entry_node)
    builder.add_node("classify", classify_node)
    builder.add_node("noop_reply", noop_reply_node)
    for workflow_id, subgraph_builder in handoff_subgraphs.items():
        builder.add_node(workflow_id, subgraph_builder().compile())

    builder.set_entry_point("entry")
    builder.add_edge("entry", "classify")
    builder.add_conditional_edges("classify", _route_after_classify)
    builder.add_edge("noop_reply", END)
    for workflow_id in handoff_subgraphs:
        builder.add_edge(workflow_id, END)

    return builder
