"""여행 계획 LangGraph 워크플로 테스트."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from api.workflows.travel_planner.lg_graph import build_lg_graph


def _compile_graph():
    return build_lg_graph().compile(checkpointer=MemorySaver())


def _make_config(thread_id: str = "test-travel"):
    return {"configurable": {"thread_id": thread_id}}


def test_full_request_completes_without_interrupt():
    """목적지와 일정이 모두 있으면 interrupt 없이 계획이 완료된다."""

    graph = _compile_graph()
    config = _make_config("full-request")

    result = graph.invoke(
        {"user_message": "도쿄 3박 4일 여행 계획 짜줘", "workflow_id": "travel_planner"},
        config,
    )

    assert "도쿄 3박 4일 여행" in result["messages"][-1].content
    assert "시부야" in result["messages"][-1].content
    assert result["destination"] == "도쿄"
    assert result["duration_text"] == "3박 4일"


def test_asks_style_when_no_destination_or_style():
    """목적지와 스타일 모두 없으면 스타일을 먼저 묻는다."""

    graph = _compile_graph()
    config = _make_config("no-info")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "workflow_id": "travel_planner"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "어떤 스타일의 여행" in reply


def test_recommends_destinations_after_style():
    """스타일 입력 후 목적지 후보를 추천한다.

    interrupt 시점에서는 노드의 return이 아직 적용되지 않으므로
    suggested_destinations는 interrupt value의 reply 내용으로 간접 확인한다.
    """

    graph = _compile_graph()
    config = _make_config("style-to-recommend")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "workflow_id": "travel_planner"},
        config,
    )

    graph.invoke(Command(resume="휴양 여행으로 추천해줘"), config)

    state = graph.get_state(config)
    assert state.tasks
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "제주" in reply
    assert "방콕" in reply
    assert "싱가포르" in reply


def test_keeps_duration_when_recommending_destination():
    """스타일과 기간을 먼저 말해도 목적지 선택 뒤 기간을 다시 묻지 않는다."""

    graph = _compile_graph()
    config = _make_config("style-duration-to-destination")

    graph.invoke(
        {"user_message": "휴양으로 2박 3일 여행 추천해줘", "workflow_id": "travel_planner"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    assert state.values["duration_text"] == "2박 3일"
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "제주" in reply

    result = graph.invoke(Command(resume="제주"), config)

    assert "제주 2박 3일 여행" in result["messages"][-1].content
    assert result["duration_text"] == "2박 3일"


def test_multi_turn_full_flow():
    """스타일 → 추천 → 목적지 선택 → 일정 → 계획 완성 전체 흐름."""

    graph = _compile_graph()
    config = _make_config("multi-turn")

    graph.invoke({"user_message": "trip plan", "workflow_id": "travel_planner"}, config)
    state = graph.get_state(config)
    assert "도시" in state.tasks[0].interrupts[0].value["reply"]

    graph.invoke(Command(resume="먹거리 위주로 가고 싶어"), config)
    state = graph.get_state(config)
    assert "오사카" in state.tasks[0].interrupts[0].value["reply"]

    graph.invoke(Command(resume="오사카"), config)
    state = graph.get_state(config)
    assert state.tasks
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "오사카" in reply
    assert "며칠" in reply

    result = graph.invoke(Command(resume="2박 3일 친구와 갈래"), config)
    assert "오사카 2박 3일 여행" in result["messages"][-1].content
    assert "도톤보리" in result["messages"][-1].content
    assert result["companion_type"] == "친구"


def test_asks_duration_when_destination_known_but_no_duration():
    """목적지만 있고 일정이 없으면 일정을 묻는다."""

    graph = _compile_graph()
    config = _make_config("no-duration")

    graph.invoke(
        {"user_message": "제주 여행 가고 싶어", "workflow_id": "travel_planner"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "제주" in reply
    assert "며칠" in reply


def test_stop_message_ends_travel_planner_conversation():
    """중간 단계에서 stop 의도가 들어오면 여행 계획 수집을 종료한다."""

    graph = _compile_graph()
    config = _make_config("travel-stop")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "workflow_id": "travel_planner"},
        config,
    )

    result = graph.invoke(Command(resume="bye"), config)

    assert result["messages"][-1].content == "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."
    assert result["destination"] == ""
    assert result["travel_style"] == ""
