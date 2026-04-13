"""__WORKFLOW_ID__ 워크플로 LangGraph를 정의한다."""

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from devtools.mcp.__WORKFLOW_ID__ import register_tools

from .lg_state import __STATE_CLASS__


def entry_node(state: __STATE_CLASS__) -> dict:
    """워크플로 진입 노드."""

    user_message = state.get("user_message", "").strip()
    return {"messages": [AIMessage(content=f"[__WORKFLOW_ID__] 메시지를 받았습니다: {user_message}")]}


def build_lg_graph() -> StateGraph:
    """워크플로 LangGraph 빌더를 반환한다."""

    register_tools()

    builder = StateGraph(__STATE_CLASS__)
    builder.add_node("entry", entry_node)
    builder.set_entry_point("entry")
    builder.add_edge("entry", END)
    return builder
