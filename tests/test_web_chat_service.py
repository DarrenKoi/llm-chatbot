"""웹 채팅 서비스 계층의 동작을 검증한다 (외부 LLM/DB 없이 mock으로)."""

from unittest.mock import call, patch

import pytest
from werkzeug.exceptions import BadRequest

from api.web_chat.models import WebChatUser
from api.web_chat.service import (
    get_conversation_messages,
    list_user_conversations,
    send_web_chat_message,
)
from api.workflows.models import WorkflowReply


@pytest.fixture()
def web_user():
    return WebChatUser(user_id="alice", user_name="Alice Kim")


@patch("api.web_chat.service.handle_message", return_value=WorkflowReply(reply="안녕하세요", workflow_id="start_chat"))
@patch("api.web_chat.service.append_message")
def test_send_message_stores_user_then_workflow_then_assistant(mock_append, mock_handle, web_user):
    reply = send_web_chat_message(web_user, "dev-channel-1", "안녕")

    assert reply.conversation_id == "dev-channel-1"
    assert reply.reply == "안녕하세요"
    assert reply.workflow_id == "start_chat"
    assert reply.message_id.startswith("web:")

    assert mock_handle.call_count == 1
    incoming = mock_handle.call_args.args[0]
    assert incoming.user_id == "alice"
    assert incoming.user_name == "Alice Kim"
    assert incoming.channel_id == "dev-channel-1"
    assert incoming.message == "안녕"
    assert incoming.message_id == reply.message_id

    inbound_call = mock_append.call_args_list[0]
    assert inbound_call == call(
        "alice",
        {"role": "user", "content": "안녕"},
        conversation_id="dev-channel-1",
        metadata={
            "channel_id": "dev-channel-1",
            "source": "web",
            "direction": "inbound",
            "user_name": "Alice Kim",
            "message_id": reply.message_id,
        },
    )
    outbound_call = mock_append.call_args_list[1]
    assert outbound_call == call(
        "alice",
        {"role": "assistant", "content": "안녕하세요"},
        conversation_id="dev-channel-1",
        metadata={
            "channel_id": "dev-channel-1",
            "source": "web",
            "direction": "outbound",
            "user_name": "Alice Kim",
            "reply_to_message_id": reply.message_id,
            "workflow_id": "start_chat",
        },
    )


@patch("api.web_chat.service.handle_message")
@patch("api.web_chat.service.append_message")
def test_workflow_failure_does_not_store_assistant_message(mock_append, mock_handle, web_user):
    mock_handle.side_effect = RuntimeError("workflow failed")

    with pytest.raises(RuntimeError):
        send_web_chat_message(web_user, "c1", "hi")

    # Only the inbound user message is stored; assistant write must not occur.
    assert mock_append.call_count == 1
    args = mock_append.call_args_list[0]
    assert args.args[1] == {"role": "user", "content": "hi"}


def test_send_message_rejects_empty_text(web_user):
    with pytest.raises(BadRequest):
        send_web_chat_message(web_user, "c1", "   ")


def test_send_message_rejects_blank_conversation_id(web_user):
    with pytest.raises(BadRequest):
        send_web_chat_message(web_user, "  ", "hi")


@patch("api.web_chat.service.list_conversations")
def test_list_user_conversations_maps_to_dto(mock_list, web_user):
    from api.conversation_service import ConversationSummary

    mock_list.return_value = [
        ConversationSummary(
            user_id="alice",
            conversation_id="c1",
            last_message_at="2026-04-25T10:00:00+00:00",
            last_message_role="assistant",
            last_message_preview="hi",
            source="web",
        ),
    ]

    result = list_user_conversations(web_user, limit=10)

    mock_list.assert_called_once_with("alice", limit=10)
    assert len(result) == 1
    assert result[0].conversation_id == "c1"
    assert result[0].source == "web"


@patch("api.web_chat.service.get_history", return_value=[{"role": "user", "content": "hi"}])
def test_get_messages_calls_history_with_user_scope(mock_history, web_user):
    messages = get_conversation_messages(web_user, "c1", limit=50)

    mock_history.assert_called_once_with("alice", conversation_id="c1", limit=50)
    assert messages == [{"role": "user", "content": "hi"}]


def test_get_messages_rejects_blank_conversation_id(web_user):
    with pytest.raises(BadRequest):
        get_conversation_messages(web_user, "  ")
