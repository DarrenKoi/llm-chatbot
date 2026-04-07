"""LangGraph 오케스트레이터 테스트."""

from unittest.mock import patch

import pytest

from api.cube.models import CubeIncomingMessage
from api.mcp import local_tools
from api.mcp import registry as mcp_registry
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


@pytest.fixture(autouse=True)
def _reset_compiled_graph():
    """각 테스트마다 컴파일된 그래프를 초기화한다."""
    import api.workflows.lg_orchestrator as mod

    mod._compiled_graph = None
    yield
    mod._compiled_graph = None


def _make_incoming(message: str, user_id: str = "test-user", channel_id: str = "ch1") -> CubeIncomingMessage:
    return CubeIncomingMessage(
        user_id=user_id,
        user_name="테스트",
        channel_id=channel_id,
        message_id="msg-1",
        message=message,
    )


@patch("api.profile.service.load_user_profile", return_value=None)
@patch("api.llm.service._get_llm")
@patch("api.conversation_service.get_history", return_value=[])
def test_handle_message_casual(mock_history, mock_llm, mock_profile):
    """일반 대화 메시지가 정상적으로 WorkflowReply를 반환한다."""

    mock_llm.return_value.invoke.return_value.content = "오케스트레이터 응답"

    from api.workflows.lg_orchestrator import handle_message

    incoming = _make_incoming("안녕하세요")
    result = handle_message(incoming)

    assert result.reply == "오케스트레이터 응답"
    assert result.workflow_id == "start_chat"


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handle_message_translator_interrupt_and_resume(mock_profile):
    """번역 요청 시 interrupt → 재개가 정상 동작한다."""

    from api.workflows.lg_orchestrator import handle_message

    result1 = handle_message(_make_incoming('"감사합니다" 번역해줘'))
    assert "영어 또는 일본어" in result1.reply
    assert result1.workflow_id == "translator"

    result2 = handle_message(_make_incoming("일본어"))
    assert "ありがとうございます" in result2.reply


@patch("api.profile.service.load_user_profile", return_value=None)
def test_handle_message_travel_planner_full_flow(mock_profile):
    """여행 계획 전체 흐름이 오케스트레이터를 통해 동작한다."""

    from api.workflows.lg_orchestrator import handle_message

    result1 = handle_message(_make_incoming("도쿄 3박 4일 여행 계획 짜줘"))
    assert result1.workflow_id == "travel_planner"
    assert "도쿄 3박 4일 여행" in result1.reply
    assert "시부야" in result1.reply
