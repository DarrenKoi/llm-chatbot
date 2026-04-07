"""차트 생성 LangGraph 워크플로 테스트."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from api.workflows.chart_maker.lg_graph import build_lg_graph


def _compile_graph():
    return build_lg_graph().compile(checkpointer=MemorySaver())


def _make_config(thread_id: str = "test-chart"):
    return {"configurable": {"thread_id": thread_id}}


def test_chart_maker_linear_flow_completes():
    """entry → collect_requirements → build_spec 선형 흐름이 완료된다."""

    graph = _compile_graph()
    config = _make_config("linear-flow")

    graph.invoke({"user_message": "차트 만들어줘", "workflow_id": "chart_maker"}, config)

    state1 = graph.get_state(config)
    assert state1.tasks, "entry에서 interrupt가 발생해야 한다"

    graph.invoke(Command(resume="bar chart"), config)

    state2 = graph.get_state(config)
    assert state2.tasks, "collect_requirements에서 interrupt가 발생해야 한다"

    result = graph.invoke(Command(resume="매출 데이터"), config)

    assert result["chart_type"] == "bar chart"
    assert result["chart_spec"] == {"chart_type": "bar chart"}
    messages = result["messages"]
    assert messages[-1].content == "차트 명세 생성 스켈레톤입니다."


def test_chart_maker_saves_chart_type_from_second_input():
    """두 번째 사용자 입력이 chart_type으로 저장된다.

    interrupt 시점에는 아직 노드가 반환되지 않았으므로,
    chart_type은 collect_requirements 완료 후(세 번째 resume) 확인한다.
    """

    graph = _compile_graph()
    config = _make_config("chart-type")

    graph.invoke({"user_message": "시각화 부탁", "workflow_id": "chart_maker"}, config)
    graph.invoke(Command(resume="pie"), config)
    result = graph.invoke(Command(resume="완성해줘"), config)

    assert result["chart_type"] == "pie"
    assert result["chart_spec"] == {"chart_type": "pie"}
