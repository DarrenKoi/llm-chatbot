"""차트 생성 LangGraph 워크플로.

기존 스텁(graph.py)과 동일한 선형 흐름을 LangGraph StateGraph로 구현한다.
entry → collect_requirements → build_spec → END
"""

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.lg_state import ChartMakerState


def entry_node(state: ChartMakerState) -> dict:
    """진입 노드. 요구사항 수집을 위해 interrupt한다."""

    user_input = interrupt({"reply": "어떤 형태의 차트를 원하시나요? 예: 막대 차트, 선 차트, pie chart"})
    return {"user_message": user_input}


def collect_requirements_node(state: ChartMakerState) -> dict:
    """차트 유형을 저장하고 추가 입력을 기다린다."""

    chart_type = state.get("user_message", "").strip()
    user_input = interrupt({"reply": "차트에 넣을 데이터를 알려주세요. 예: 월별 매출, 분기별 사용자 수"})
    return {"chart_type": chart_type, "user_message": user_input}


def build_spec_node(state: ChartMakerState) -> dict:
    """차트 명세를 생성한다."""

    chart_type = state.get("chart_type") or "bar"
    reply = "차트 명세 생성 스켈레톤입니다."

    return {
        "messages": [AIMessage(content=reply)],
        "chart_spec": {"chart_type": chart_type},
    }


def build_lg_graph() -> StateGraph:
    """차트 생성 워크플로 LangGraph StateGraph 빌더를 반환한다."""

    builder = StateGraph(ChartMakerState)

    builder.add_node("entry", entry_node)
    builder.add_node("collect_requirements", collect_requirements_node)
    builder.add_node("build_spec", build_spec_node)

    builder.set_entry_point("entry")
    builder.add_edge("entry", "collect_requirements")
    builder.add_edge("collect_requirements", "build_spec")
    builder.add_edge("build_spec", END)

    return builder
