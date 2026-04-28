"""LangGraph 오케스트레이터 테스트."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.cube.models import CubeIncomingMessage
from api.mcp_runtime import local_tools
from api.mcp_runtime import registry as mcp_registry
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


class _FakeTask:
    def __init__(self, *, interrupts: tuple[object, ...] = (), name: str | None = None, path: object = None) -> None:
        self.interrupts = interrupts
        self.name = name
        self.path = path


class _FakeSnapshot:
    def __init__(
        self,
        *,
        values: dict | None = None,
        tasks: tuple[object, ...] = (),
        next_nodes: tuple[str, ...] = (),
    ) -> None:
        self.values = values or {}
        self.tasks = tasks
        self.next = next_nodes


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
def test_handle_message_translator_interrupt_and_resume(mock_profile, monkeypatch):
    """번역 요청 시 interrupt → 재개가 정상 동작한다."""

    decisions = iter(
        [
            {
                "action": "ask_user",
                "source_text": "감사합니다",
                "target_language": "",
                "missing_slot": "target_language",
                "reply": "",
            },
            {
                "action": "translate",
                "source_text": "감사합니다",
                "target_language": "일본어",
                "missing_slot": "",
                "reply": "",
            },
        ]
    )
    monkeypatch.setattr("api.workflows.translator.llm_decision.generate_json_reply", lambda **kwargs: next(decisions))

    from api.workflows.lg_orchestrator import handle_message

    result1 = handle_message(_make_incoming('"감사합니다" 번역해줘'))
    assert "어떤 언어로 번역할까요?" in result1.reply
    assert result1.workflow_id == "translator"

    result2 = handle_message(_make_incoming("일본어"))
    assert "ありがとうございます" in result2.reply


@patch("api.workflows.lg_orchestrator.log_workflow_activity")
@patch("api.workflows.lg_orchestrator._get_graph")
def test_handle_message_logs_user_name_and_waiting_state(mock_get_graph, mock_log_workflow_activity):
    from api.workflows.lg_orchestrator import handle_message

    interrupt = SimpleNamespace(value={"reply": "목표 언어를 알려주세요."})
    fake_graph = mock_get_graph.return_value
    fake_graph.get_state.side_effect = [
        _FakeSnapshot(next_nodes=("entry",)),
        _FakeSnapshot(
            values={"active_workflow": "translator", "last_asked_slot": "target_language"},
            tasks=(
                _FakeTask(
                    interrupts=(interrupt,),
                    name="collect_target_language",
                    path=("translator", "collect_target_language"),
                ),
            ),
            next_nodes=("collect_target_language",),
        ),
    ]

    result = handle_message(_make_incoming('"감사합니다" 번역해줘'))

    assert result.reply == "목표 언어를 알려주세요."
    assert result.workflow_id == "translator"
    fake_graph.invoke.assert_called_once_with(
        {
            "user_message": '"감사합니다" 번역해줘',
            "user_id": "test-user",
            "channel_id": "ch1",
        },
        {"configurable": {"thread_id": "test-user::ch1"}},
    )
    assert mock_log_workflow_activity.call_count == 2

    received_call = mock_log_workflow_activity.call_args_list[0]
    assert received_call.args == ("start_chat", "workflow_message_received")
    assert received_call.kwargs["user_id"] == "test-user"
    assert received_call.kwargs["user_name"] == "테스트"
    assert received_call.kwargs["status"] == "active"
    assert received_call.kwargs["user_state"] == "entry"

    processed_call = mock_log_workflow_activity.call_args_list[1]
    assert processed_call.args == ("translator", "workflow_message_processed")
    assert processed_call.kwargs["user_id"] == "test-user"
    assert processed_call.kwargs["user_name"] == "테스트"
    assert processed_call.kwargs["status"] == "waiting_user_input"
    assert processed_call.kwargs["user_state"] == "waiting_for_target_language"
    assert processed_call.kwargs["waiting_for"] == "target_language"
    assert processed_call.kwargs["node_id"] == "collect_target_language"
    assert processed_call.kwargs["resumed_from_interrupt"] is False


@patch("api.workflows.lg_orchestrator.log_workflow_activity")
@patch("api.workflows.lg_orchestrator._get_graph")
def test_handle_message_logs_resume_and_completion_state(mock_get_graph, mock_log_workflow_activity):
    from api.workflows.lg_orchestrator import handle_message

    waiting_interrupt = SimpleNamespace(value={"reply": "목표 언어를 알려주세요."})
    fake_graph = mock_get_graph.return_value
    fake_graph.get_state.side_effect = [
        _FakeSnapshot(
            values={"active_workflow": "translator", "last_asked_slot": "target_language"},
            tasks=(
                _FakeTask(
                    interrupts=(waiting_interrupt,),
                    name="collect_target_language",
                    path=("translator", "collect_target_language"),
                ),
            ),
            next_nodes=("collect_target_language",),
        ),
        _FakeSnapshot(
            values={
                "active_workflow": "translator",
                "messages": [SimpleNamespace(content="ありがとうございます")],
            }
        ),
    ]

    result = handle_message(_make_incoming("일본어"))

    assert result.reply == "ありがとうございます"
    assert result.workflow_id == "translator"
    invoke_args = fake_graph.invoke.call_args.args
    assert type(invoke_args[0]).__name__ == "Command"
    assert invoke_args[1] == {"configurable": {"thread_id": "test-user::ch1"}}
    assert mock_log_workflow_activity.call_count == 2

    received_call = mock_log_workflow_activity.call_args_list[0]
    assert received_call.args == ("translator", "workflow_message_received")
    assert received_call.kwargs["status"] == "waiting_user_input"
    assert received_call.kwargs["user_state"] == "waiting_for_target_language"
    assert received_call.kwargs["resumed_from_interrupt"] is True

    processed_call = mock_log_workflow_activity.call_args_list[1]
    assert processed_call.args == ("translator", "workflow_message_processed")
    assert processed_call.kwargs["status"] == "completed"
    assert processed_call.kwargs["reply_length"] == len("ありがとうございます")
    assert processed_call.kwargs["resumed_from_interrupt"] is True
