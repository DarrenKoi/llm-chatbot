"""웹 채팅 라우터의 endpoint 동작을 검증한다."""

from unittest.mock import patch

import pytest

from api import config
from api.web_chat.models import WebChatReply
from api.workflows.models import WorkflowReply


@pytest.fixture(autouse=True)
def _disable_localhost_dev_fallback():
    """기본적으로 localhost dev 사용자 폴백을 끄고, 테스트가 cookie 동작만 검증하도록 한다."""
    with patch.object(config, "WEB_CHAT_DEV_USER", ""):
        yield


def _set_lastuser(client, user_id: str = "alice", user_name: str = "Alice Kim") -> None:
    client.set_cookie("LASTUSER", user_id, domain="localhost")
    client.set_cookie("LASTUSERNAME", user_name, domain="localhost")


def test_me_returns_current_user(client):
    _set_lastuser(client)

    response = client.get("/api/v1/web-chat/me")

    assert response.status_code == 200
    assert response.get_json() == {"user_id": "alice", "user_name": "Alice Kim"}


def test_me_returns_401_without_cookie(client):
    response = client.get("/api/v1/web-chat/me")

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"] == "unauthorized"


@patch("api.web_chat.router.list_user_conversations", return_value=[])
def test_conversations_endpoint_uses_authenticated_user(mock_list, client):
    _set_lastuser(client)

    response = client.get("/api/v1/web-chat/conversations")

    assert response.status_code == 200
    assert response.get_json() == {"conversations": []}
    mock_list.assert_called_once()
    user_arg = mock_list.call_args.args[0]
    assert user_arg.user_id == "alice"


@patch("api.web_chat.router.get_conversation_messages", return_value=[{"role": "user", "content": "hi"}])
def test_messages_endpoint_returns_history(mock_get_messages, client):
    _set_lastuser(client)

    response = client.get("/api/v1/web-chat/conversations/c1/messages")

    assert response.status_code == 200
    body = response.get_json()
    assert body["conversation_id"] == "c1"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


@patch(
    "api.web_chat.router.send_web_chat_message",
    return_value=WebChatReply(
        conversation_id="c1",
        message_id="web:abc",
        reply="hi",
        workflow_id="start_chat",
    ),
)
def test_post_message_passes_authenticated_user_and_text(mock_send, client):
    _set_lastuser(client)

    response = client.post(
        "/api/v1/web-chat/conversations/c1/messages",
        json={"message": "안녕", "user_id": "evil", "user_name": "evil"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["reply"] == "hi"
    assert body["message_id"] == "web:abc"
    user_arg, conv_arg, text_arg = mock_send.call_args.args
    assert user_arg.user_id == "alice"
    assert user_arg.user_name == "Alice Kim"
    assert conv_arg == "c1"
    assert text_arg == "안녕"


@patch("api.web_chat.router.send_web_chat_message")
def test_post_message_rejects_non_json_body(mock_send, client):
    _set_lastuser(client)

    response = client.post(
        "/api/v1/web-chat/conversations/c1/messages",
        data="plain text",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "bad_request"
    mock_send.assert_not_called()


@patch("api.web_chat.router.handle_message_send_failure_logger", create=True)
@patch("api.web_chat.router.send_web_chat_message", side_effect=RuntimeError("workflow boom"))
def test_post_message_returns_502_when_workflow_fails(mock_send, _logger, client):
    _set_lastuser(client)

    response = client.post(
        "/api/v1/web-chat/conversations/c1/messages",
        json={"message": "hi"},
    )

    assert response.status_code == 502
    body = response.get_json()
    assert body["error"] == "workflow_failed"


def test_endpoints_require_lastuser_cookie(client):
    paths = [
        ("get", "/api/v1/web-chat/me"),
        ("get", "/api/v1/web-chat/conversations"),
        ("get", "/api/v1/web-chat/conversations/c1/messages"),
    ]
    for method, path in paths:
        response = client.open(path, method=method.upper())
        assert response.status_code == 401, path

    response = client.post("/api/v1/web-chat/conversations/c1/messages", json={"message": "hi"})
    assert response.status_code == 401


@patch(
    "api.web_chat.router.send_web_chat_message",
    return_value=WebChatReply(
        conversation_id="c1",
        message_id="web:abc",
        reply="hi",
        workflow_id="start_chat",
    ),
)
def test_post_message_ignores_user_id_in_body(mock_send, client):
    _set_lastuser(client, user_id="alice")

    client.post(
        "/api/v1/web-chat/conversations/c1/messages",
        json={"message": "hi", "user_id": "bob"},
    )

    user_arg = mock_send.call_args.args[0]
    assert user_arg.user_id == "alice"


@patch("api.web_chat.service.handle_message", return_value=WorkflowReply(reply="네", workflow_id="start_chat"))
def test_full_stack_with_mocked_workflow_returns_reply(_handle_message, client):
    """라우터→서비스 통합 흐름: LASTUSER가 user_id로 사용되고 reply가 정상 반환됨을 확인."""
    _set_lastuser(client, user_id="alice")
    response = client.post(
        "/api/v1/web-chat/conversations/c1/messages",
        json={"message": "hi"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["reply"] == "네"
    assert body["workflow_id"] == "start_chat"
    assert body["conversation_id"] == "c1"
