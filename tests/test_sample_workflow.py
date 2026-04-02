"""샘플 번역 워크플로 end-to-end 테스트."""

from unittest.mock import patch

import pytest

from api.mcp import local_tools, registry as mcp_registry
from api.workflows.orchestrator import run_graph
from api.workflows.sample.graph import build_graph
from api.workflows.sample.state import SampleWorkflowState
from api.workflows.sample.tools import register_sample_tools


@pytest.fixture(autouse=True)
def _clean_mcp():
    """테스트 전후로 MCP 레지스트리와 로컬 핸들러를 정리한다."""

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()

    register_sample_tools()

    yield

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()


def _make_state(node_id: str = "entry") -> SampleWorkflowState:
    return SampleWorkflowState(
        user_id="test_user",
        workflow_id="sample",
        node_id=node_id,
        data={},
    )


def test_translate_tool_korean_to_english():
    """translate 도구가 한국어를 영어로 번역하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(
        MCPToolCall(tool_id="translate", arguments={"text": "안녕하세요", "target_language": "영어"}),
    )

    assert result.success is True
    assert result.output["source"] == "ko"
    assert result.output["target"] == "en"
    assert result.output["result"] == "Hello"


def test_translate_tool_korean_to_japanese():
    """translate 도구가 한국어를 일본어로 번역하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(
        MCPToolCall(tool_id="translate", arguments={"text": "안녕하세요", "target_language": "일본어"}),
    )

    assert result.success is True
    assert result.output["source"] == "ko"
    assert result.output["target"] == "ja"
    assert result.output["result"] == "こんにちは"


def test_sample_workflow_completes_when_target_language_is_explicit():
    """목표 언어가 명시되면 바로 번역 완료까지 진행한다."""

    state = _make_state()
    reply = run_graph(build_graph(), state, '"안녕하세요"를 일본어로 번역해줘')

    assert reply == "こんにちは"
    assert state.status == "completed"
    assert state.data["source_text"] == "안녕하세요"
    assert state.data["target_language"] == "ja"
    assert state.data["translation_direction"] == "ko→ja"


def test_sample_workflow_waits_for_target_language_when_missing():
    """목표 언어가 없으면 재질문하고 waiting 상태로 멈춘다."""

    state = _make_state()
    reply = run_graph(build_graph(), state, '"안녕하세요" 번역해줘')

    assert "영어 또는 일본어" in reply
    assert state.status == "waiting_user_input"
    assert state.node_id == "collect_target_language"
    assert state.data["source_text"] == "안녕하세요"
    assert state.data["last_asked_slot"] == "target_language"


def test_sample_workflow_resumes_after_follow_up_answer():
    """재질문 후 다음 사용자 턴에서 목표 언어를 받으면 이어서 완료한다."""

    state = _make_state()
    first_reply = run_graph(build_graph(), state, '"안녕하세요" 번역해줘')

    assert "영어 또는 일본어" in first_reply
    assert state.status == "waiting_user_input"

    second_reply = run_graph(build_graph(), state, "영어")

    assert second_reply == "Hello"
    assert state.status == "completed"
    assert state.data["target_language"] == "en"
    assert state.data["translation_direction"] == "ko→en"
    assert state.data["translated"] == "Hello"


def test_handle_message_with_sample_workflow_waits_for_clarification():
    """handle_message 경유 시에도 재질문 응답과 waiting 상태가 저장된다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    incoming = CubeIncomingMessage(
        user_id="test_integration",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        message='"감사합니다" 번역해줘',
    )

    with patch("api.workflows.orchestrator.load_state", return_value=None), \
         patch("api.workflows.orchestrator.save_state") as mock_save, \
         patch("api.workflows.orchestrator.DEFAULT_WORKFLOW_ID", "sample"):

        reply = handle_message(incoming)

    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert "영어 또는 일본어" in reply
    assert saved_state.status == "waiting_user_input"
    assert saved_state.node_id == "collect_target_language"
    assert saved_state.data["source_text"] == "감사합니다"


def test_handle_message_with_sample_workflow_resumes_saved_state():
    """저장된 sample 상태가 다음 턴에서 이어서 완료된다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    waiting_state = SampleWorkflowState(
        user_id="test_resume",
        workflow_id="sample",
        node_id="collect_target_language",
        status="waiting_user_input",
        source_text="감사합니다",
        data={
            "source_text": "감사합니다",
            "last_asked_slot": "target_language",
        },
    )
    incoming = CubeIncomingMessage(
        user_id="test_resume",
        user_name="tester",
        channel_id="c1",
        message_id="m2",
        message="일본어",
    )

    with patch("api.workflows.orchestrator.load_state", return_value=waiting_state), \
         patch("api.workflows.orchestrator.save_state") as mock_save, \
         patch("api.workflows.orchestrator.DEFAULT_WORKFLOW_ID", "sample"):

        reply = handle_message(incoming)

    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert reply == "ありがとうございます"
    assert saved_state.status == "completed"
    assert saved_state.data["target_language"] == "ja"
    assert saved_state.data["translation_direction"] == "ko→ja"
