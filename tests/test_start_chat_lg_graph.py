"""시작 대화 LangGraph 워크플로 테스트.

서브그래프를 통한 자식 워크플로 핸드오프와 일반 대화 흐름을 검증한다.
"""

from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from api.mcp import local_tools
from api.mcp import registry as mcp_registry
from api.workflows.start_chat.lg_graph import _get_handoff_subgraph_builders, build_lg_graph
from api.workflows.translator.tools import register_translator_tools


@pytest.fixture(autouse=True)
def _clean_mcp():
    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()
    register_translator_tools()
    yield
    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()


def _compile_graph():
    return build_lg_graph().compile(checkpointer=MemorySaver())


def _make_config(thread_id: str = "test-start-chat"):
    return {"configurable": {"thread_id": thread_id}}


@patch("api.profile.service.load_user_profile", return_value=None)
@patch("api.llm.service._get_llm")
@patch("api.conversation_service.get_history", return_value=[])
def test_casual_conversation_completes(mock_history, mock_llm, mock_profile):
    """일반 대화는 entry → classify → retrieve → plan → generate → END 순으로 완료된다."""

    mock_llm.return_value.invoke.return_value.content = "테스트 응답입니다."

    graph = _compile_graph()
    config = _make_config("casual")

    result = graph.invoke(
        {"user_message": "안녕하세요", "user_id": "user1", "workflow_id": "start_chat"},
        config,
    )

    assert result["detected_intent"] == "start_chat"
    assert result["messages"][-1].content == "테스트 응답입니다."


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handoff_to_translator_subgraph(mock_profile):
    """번역 키워드가 있으면 translator 서브그래프로 분기하고 interrupt된다."""

    graph = _compile_graph()
    config = _make_config("handoff-translator")

    graph.invoke(
        {"user_message": '"안녕하세요" 번역해줘', "user_id": "user1", "workflow_id": "start_chat"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks, "translator 서브그래프에서 interrupt가 발생해야 한다"
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "영어 또는 일본어" in reply
    assert state.values["detected_intent"] == "translator"

    result = graph.invoke(Command(resume="영어"), config)

    assert result["messages"][-1].content == "Hello"


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handoff_to_travel_planner_subgraph(mock_profile):
    """여행 키워드가 있으면 travel_planner 서브그래프로 분기한다."""

    graph = _compile_graph()
    config = _make_config("handoff-travel")

    result = graph.invoke(
        {"user_message": "도쿄 3박 4일 여행 계획 짜줘", "user_id": "user1", "workflow_id": "start_chat"},
        config,
    )

    assert result["detected_intent"] == "travel_planner"
    assert "도쿄 3박 4일 여행" in result["messages"][-1].content
    assert "시부야" in result["messages"][-1].content


@patch("api.profile.service.load_user_profile", return_value=None)
def test_travel_planner_multi_turn_via_start_chat(mock_profile):
    """start_chat → travel_planner 서브그래프 멀티턴 interrupt/resume 흐름."""

    graph = _compile_graph()
    config = _make_config("travel-multi-turn")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "user_id": "user1", "workflow_id": "start_chat"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    assert "스타일" in state.tasks[0].interrupts[0].value["reply"]

    graph.invoke(Command(resume="휴양 여행"), config)

    state2 = graph.get_state(config)
    assert state2.tasks
    reply2 = state2.tasks[0].interrupts[0].value["reply"]
    assert "제주" in reply2

    graph.invoke(Command(resume="제주"), config)

    state3 = graph.get_state(config)
    assert state3.tasks
    assert "며칠" in state3.tasks[0].interrupts[0].value["reply"]

    result = graph.invoke(Command(resume="2박 3일"), config)

    assert "제주 2박 3일 여행" in result["messages"][-1].content


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handoff_to_chart_maker_subgraph(mock_profile):
    """차트 키워드가 있으면 chart_maker 서브그래프로 분기한다."""

    graph = _compile_graph()
    config = _make_config("handoff-chart")

    graph.invoke(
        {"user_message": "차트 만들어줘", "user_id": "user1", "workflow_id": "start_chat"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks, "chart_maker 서브그래프에서 interrupt가 발생해야 한다"

    graph.invoke(Command(resume="bar chart"), config)

    state2 = graph.get_state(config)
    assert state2.tasks

    result = graph.invoke(Command(resume="매출 데이터"), config)

    assert result["messages"][-1].content == "차트 명세 생성 스켈레톤입니다."


def test_handoff_subgraph_builders_are_loaded_from_registry(monkeypatch):
    def _fake_builder():
        raise AssertionError("builder should not be executed in this unit test")

    monkeypatch.setattr(
        "api.workflows.registry.list_handoff_workflows",
        lambda: [
            {"workflow_id": "custom", "build_lg_graph": _fake_builder, "handoff_keywords": ("custom",)},
            {"workflow_id": "legacy", "handoff_keywords": ("legacy",)},
        ],
    )

    builders = _get_handoff_subgraph_builders()

    assert builders == {"custom": _fake_builder}
