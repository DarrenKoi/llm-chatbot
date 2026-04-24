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
    """일반 대화는 entry → classify → retrieve → generate → END 순으로 완료된다."""

    mock_llm.return_value.invoke.return_value.content = "테스트 응답입니다."

    graph = _compile_graph()
    config = _make_config("casual")

    result = graph.invoke(
        {
            "user_message": "안녕하세요",
            "user_id": "user1",
        },
        config,
    )

    assert result["active_workflow"] == "start_chat"
    assert result["messages"][-1].content == "테스트 응답입니다."


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handoff_to_translator_subgraph(mock_profile, monkeypatch):
    """번역 키워드가 있으면 translator 서브그래프로 분기하고 interrupt된다."""

    decisions = iter(
        [
            {
                "action": "ask_user",
                "source_text": "안녕하세요",
                "target_language": "",
                "missing_slot": "target_language",
                "reply": "",
            },
            {
                "action": "translate",
                "source_text": "안녕하세요",
                "target_language": "영어",
                "missing_slot": "",
                "reply": "",
            },
        ]
    )
    monkeypatch.setattr("api.workflows.translator.llm_decision.generate_json_reply", lambda **kwargs: next(decisions))

    graph = _compile_graph()
    config = _make_config("handoff-translator")

    graph.invoke(
        {
            "user_message": '"안녕하세요" 번역해줘',
            "user_id": "user1",
        },
        config,
    )

    state = graph.get_state(config)
    assert state.tasks, "translator 서브그래프에서 interrupt가 발생해야 한다"
    reply = state.tasks[0].interrupts[0].value["reply"]
    assert "어떤 언어로 번역할까요?" in reply
    assert state.values["active_workflow"] == "translator"

    result = graph.invoke(Command(resume="영어"), config)

    assert "Hello" in result["messages"][-1].content
    assert "헬로" in result["messages"][-1].content


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
