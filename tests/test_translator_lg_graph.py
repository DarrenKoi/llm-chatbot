"""번역 서비스 LangGraph 워크플로 테스트.

LangGraph StateGraph + MemorySaver를 사용해 interrupt/resume 흐름을
기존 커스텀 그래프와 동일하게 검증한다.
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from api.mcp_runtime import local_tools
from api.mcp_runtime import registry as mcp_registry
from api.workflows.translator.lg_graph import build_lg_graph
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
    checkpointer = MemorySaver()
    return build_lg_graph().compile(checkpointer=checkpointer)


def _make_config(thread_id: str = "test-thread"):
    return {"configurable": {"thread_id": thread_id}}


def test_full_translation_completes_without_interrupt():
    """원문과 목표 언어가 모두 있으면 interrupt 없이 번역이 완료된다."""

    graph = _compile_graph()
    config = _make_config("full-translate")

    result = graph.invoke(
        {"user_message": '"안녕하세요"를 일본어로 번역해줘', "workflow_id": "translator"},
        config,
    )

    assert result["translated"] == "こんにちは"
    assert result["source_text"] == "안녕하세요"
    assert result["target_language"] == "ja"
    assert result["translation_direction"] == "ko→ja"
    assert result["pronunciation_ko"] == "곤니치와"

    messages = result["messages"]
    assert messages[-1].content == "こんにちは\n(한국어 발음: 곤니치와)"


def test_interrupt_for_missing_target_language():
    """목표 언어가 없으면 interrupt되고, 재개 시 번역이 완료된다."""

    graph = _compile_graph()
    config = _make_config("missing-target")

    graph.invoke(
        {"user_message": '"안녕하세요" 번역해줘', "workflow_id": "translator"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks, "interrupt가 발생해야 한다"
    interrupt_value = state.tasks[0].interrupts[0].value
    assert "영어" in interrupt_value["reply"]
    assert "일본어" in interrupt_value["reply"]
    assert "중국어" in interrupt_value["reply"]

    result = graph.invoke(Command(resume="영어"), config)

    assert result["translated"] == "Hello"
    assert result["target_language"] == "en"
    assert result["translation_direction"] == "ko→en"
    assert result["pronunciation_ko"] == "헬로"


def test_interrupt_for_missing_source_text():
    """원문이 없으면 interrupt되고, 재개 시 원문을 수집한다.

    last_asked_slot이 source_text이면 원문만 추출하고 목표 언어는
    별도 단계에서 수집한다 (기존 커스텀 그래프와 동일한 동작).
    """

    graph = _compile_graph()
    config = _make_config("missing-source")

    graph.invoke(
        {"user_message": "번역해줘", "workflow_id": "translator"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks, "interrupt가 발생해야 한다"
    interrupt_value = state.tasks[0].interrupts[0].value
    assert "번역할 문장" in interrupt_value["reply"]

    graph.invoke(Command(resume="감사합니다"), config)

    state2 = graph.get_state(config)
    assert state2.tasks, "목표 언어 interrupt가 발생해야 한다"
    assert state2.values["source_text"] == "감사합니다"

    result = graph.invoke(Command(resume="영어"), config)

    assert result["translated"] == "Thank you"
    assert result["target_language"] == "en"


def test_double_interrupt_source_then_target():
    """원문과 목표 언어가 모두 없으면 두 번 interrupt된다."""

    graph = _compile_graph()
    config = _make_config("double-interrupt")

    graph.invoke(
        {"user_message": "번역해줘", "workflow_id": "translator"},
        config,
    )

    state1 = graph.get_state(config)
    assert state1.tasks
    assert "번역할 문장" in state1.tasks[0].interrupts[0].value["reply"]

    graph.invoke(Command(resume="안녕하세요"), config)

    state2 = graph.get_state(config)
    assert state2.tasks, "목표 언어 interrupt가 발생해야 한다"
    target_reply = state2.tasks[0].interrupts[0].value["reply"]
    assert "영어" in target_reply
    assert "일본어" in target_reply

    result = graph.invoke(Command(resume="일본어"), config)

    assert result["translated"] == "こんにちは"
    assert result["translation_direction"] == "ko→ja"


def test_source_prompt_accepts_full_translation_request():
    """원문 질문에 문장과 언어를 함께 답하면 추가 질문 없이 번역한다."""

    graph = _compile_graph()
    config = _make_config("source-with-language")

    graph.invoke(
        {"user_message": "번역해줘", "workflow_id": "translator"},
        config,
    )

    result = graph.invoke(Command(resume='"감사합니다"를 영어로 번역해줘'), config)

    assert result["translated"] == "Thank you"
    assert result["source_text"] == "감사합니다"
    assert result["target_language"] == "en"


def test_stop_message_ends_translation_conversation():
    """중간 단계에서 stop 의도가 들어오면 정중히 종료한다."""

    graph = _compile_graph()
    config = _make_config("translator-stop")

    graph.invoke(
        {"user_message": '"안녕하세요" 번역해줘', "workflow_id": "translator"},
        config,
    )

    result = graph.invoke(Command(resume="stop"), config)

    assert result["messages"][-1].content == "번역은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."
    assert result["source_text"] == ""
    assert result["target_language"] == ""


def test_english_translation_request():
    """영문 요청도 올바르게 파싱해 번역을 완료한다."""

    graph = _compile_graph()
    config = _make_config("english-request")

    result = graph.invoke(
        {"user_message": 'translate "hello" to japanese', "workflow_id": "translator"},
        config,
    )

    assert result["translated"] == "こんにちは"
    assert result["source_text"] == "hello"
    assert result["target_language"] == "ja"
    assert result["translation_direction"] == "en→ja"
