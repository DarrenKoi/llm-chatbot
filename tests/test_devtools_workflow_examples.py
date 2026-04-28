"""devtools LangGraph 워크플로 예제의 회귀 동작을 검증한다."""

from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from devtools.workflows.travel_planner_example import build_lg_graph as build_travel_graph


def _compile_graph(builder):
    return builder().compile(checkpointer=MemorySaver())


def _make_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def test_travel_planner_example_completes_after_collecting_missing_info():
    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-complete")

    graph.invoke(
        {"user_message": "오사카 여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    result = graph.invoke(Command(resume="2박 3일"), config)

    assert "오사카 2박 3일 여행" in result["messages"][-1].content


def test_travel_planner_example_stop_message_completes_cleanly():
    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-stop")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    result = graph.invoke(Command(resume="bye"), config)

    assert result["messages"][-1].content == "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."


@patch("devtools.workflows.travel_planner_example.lg_graph.recommend_destinations", return_value=["제주", "삿포로"])
def test_travel_planner_example_interrupts_with_recommendation(mock_recommend):
    del mock_recommend

    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-recommend")

    graph.invoke(
        {"user_message": "휴양 여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    assert "제주, 삿포로" in state.tasks[0].interrupts[0].value["reply"]
