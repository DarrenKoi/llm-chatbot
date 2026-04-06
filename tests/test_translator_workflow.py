"""번역 서비스 워크플로 end-to-end 테스트."""

import json
import logging
from unittest.mock import patch

import pytest

from api import config
from api.mcp import local_tools
from api.mcp import registry as mcp_registry
from api.utils.logger import get_workflow_logger
from api.workflows.orchestrator import run_graph
from api.workflows.translator.graph import build_graph
from api.workflows.translator.state import TranslatorWorkflowState
from api.workflows.translator.tools import register_translator_tools


@pytest.fixture(autouse=True)
def _clean_mcp():
    """테스트 전후로 MCP 레지스트리와 로컬 핸들러를 정리한다."""

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()

    register_translator_tools()

    yield

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()


def _make_state(node_id: str = "entry") -> TranslatorWorkflowState:
    return TranslatorWorkflowState(
        user_id="test_user",
        workflow_id="translator",
        node_id=node_id,
        data={},
    )


def _reset_workflow_loggers() -> None:
    from api.utils.logger import service as logger_service

    logger_service._setup_done = False
    manager = logging.root.manager
    for name, logger_obj in manager.loggerDict.items():
        if not isinstance(logger_obj, logging.Logger) or not name.startswith("workflow."):
            continue
        for handler in list(logger_obj.handlers):
            if getattr(handler, "_chatbot_handler_tag", "").startswith("chatbot."):
                logger_obj.removeHandler(handler)
                handler.close()


def _flush_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


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


def test_translate_tool_is_registered_with_workflow_tags():
    tool = mcp_registry.get_tool("translate")

    assert tool.tags == ("translation", "language")


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
    assert result.output["pronunciation_ko"] == "곤니치와"


def test_translator_workflow_completes_when_target_language_is_explicit():
    """목표 언어가 명시되면 바로 번역 완료까지 진행한다."""

    state = _make_state()
    reply = run_graph(build_graph(), state, '"안녕하세요"를 일본어로 번역해줘')

    assert reply == "こんにちは\n(한국어 발음: 곤니치와)"
    assert state.status == "completed"
    assert state.data["source_text"] == "안녕하세요"
    assert state.data["target_language"] == "ja"
    assert state.data["translation_direction"] == "ko→ja"
    assert state.data["pronunciation_ko"] == "곤니치와"


def test_translator_workflow_writes_structured_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "LOG_TIMEZONE", "Asia/Seoul")
    monkeypatch.setattr(config, "LOG_RETENTION_DAYS", 7)
    _reset_workflow_loggers()

    state = _make_state()
    reply = run_graph(build_graph(), state, '"안녕하세요"를 영어로 번역해줘')

    assert reply == "Hello"
    workflow_logger = get_workflow_logger("translator")
    _flush_handlers(workflow_logger)

    workflow_log_file = config.LOG_DIR / "workflows" / "translator" / "events.jsonl"
    assert workflow_log_file.exists()
    log_lines = workflow_log_file.read_text(encoding="utf-8").splitlines()
    payloads = [json.loads(line) for line in log_lines]
    events = [payload["event"] for payload in payloads]

    assert "workflow_step_started" in events
    assert "workflow_step_completed" in events
    assert "workflow_run_finished" in events
    assert any(
        payload.get("action") == "complete" for payload in payloads if payload["event"] == "workflow_step_completed"
    )


def test_translator_workflow_completes_for_english_request():
    """영문 요청도 목표 언어를 올바르게 파싱해 완료한다."""

    state = _make_state()
    reply = run_graph(build_graph(), state, 'translate "hello" to japanese')

    assert reply == "こんにちは\n(한국어 발음: 곤니치와)"
    assert state.status == "completed"
    assert state.data["source_text"] == "hello"
    assert state.data["target_language"] == "ja"
    assert state.data["translation_direction"] == "en→ja"
    assert state.data["pronunciation_ko"] == "곤니치와"


def test_translator_workflow_waits_for_target_language_when_missing():
    """목표 언어가 없으면 재질문하고 waiting 상태로 멈춘다."""

    state = _make_state()
    reply = run_graph(build_graph(), state, '"안녕하세요" 번역해줘')

    assert "영어 또는 일본어" in reply
    assert state.status == "waiting_user_input"
    assert state.node_id == "collect_target_language"
    assert state.data["source_text"] == "안녕하세요"
    assert state.data["last_asked_slot"] == "target_language"


def test_translator_workflow_resumes_after_follow_up_answer():
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


def test_translator_workflow_reuses_previous_source_for_language_only_follow_up():
    """완료 직후 언어만 바꿔 요청하면 직전 원문을 다시 사용한다."""

    state = _make_state()
    first_reply = run_graph(build_graph(), state, '"안녕하세요"를 일본어로 번역해줘')

    assert first_reply == "こんにちは\n(한국어 발음: 곤니치와)"
    assert state.status == "completed"
    assert state.node_id == "entry"

    second_reply = run_graph(build_graph(), state, "이번엔 영어로 번역해줘")

    assert second_reply == "Hello"
    assert state.status == "completed"
    assert state.data["source_text"] == "안녕하세요"
    assert state.data["target_language"] == "en"
    assert state.data["translation_direction"] == "ko→en"


def test_translator_workflow_does_not_reuse_previous_target_for_new_source_text():
    """완료 후 새 원문만 주어지면 이전 목표 언어를 재사용하지 않는다."""

    state = _make_state()
    first_reply = run_graph(build_graph(), state, '"안녕하세요"를 일본어로 번역해줘')

    assert first_reply == "こんにちは\n(한국어 발음: 곤니치와)"
    assert state.status == "completed"

    second_reply = run_graph(build_graph(), state, '"감사합니다" 번역해줘')

    assert "영어 또는 일본어" in second_reply
    assert state.status == "waiting_user_input"
    assert state.node_id == "collect_target_language"
    assert state.data["source_text"] == "감사합니다"
    assert state.data["target_language"] == ""


def test_handle_message_with_translator_workflow_waits_for_clarification():
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

    with (
        patch("api.workflows.orchestrator.load_state", return_value=None),
        patch("api.workflows.orchestrator.save_state") as mock_save,
        patch("api.workflows.orchestrator.DEFAULT_WORKFLOW_ID", "translator"),
    ):
        reply = handle_message(incoming)

    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert "영어 또는 일본어" in reply
    assert saved_state.status == "waiting_user_input"
    assert saved_state.node_id == "collect_target_language"
    assert saved_state.data["source_text"] == "감사합니다"


def test_handle_message_with_translator_workflow_resumes_saved_state():
    """저장된 translator 상태가 다음 턴에서 이어서 완료된다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    waiting_state = TranslatorWorkflowState(
        user_id="test_resume",
        workflow_id="translator",
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

    with (
        patch("api.workflows.orchestrator.load_state", return_value=waiting_state),
        patch("api.workflows.orchestrator.save_state") as mock_save,
        patch("api.workflows.orchestrator.DEFAULT_WORKFLOW_ID", "translator"),
    ):
        reply = handle_message(incoming)

    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert reply == "ありがとうございます\n(한국어 발음: 아리가토고자이마스)"
    assert saved_state.status == "completed"
    assert saved_state.data["target_language"] == "ja"
    assert saved_state.data["translation_direction"] == "ko→ja"
    assert saved_state.data["pronunciation_ko"] == "아리가토고자이마스"
