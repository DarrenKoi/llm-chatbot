from unittest.mock import call, patch

import pytest

from api import config
from api.cube.queue import CubeQueueError
from api.cube.service import (
    CubePayloadError,
    CubeQueueUnavailableError,
    CubeUpstreamError,
    accept_cube_message,
    handle_cube_message,
)


@patch("api.cube.service.log_request")
@patch("api.cube.service.enqueue_incoming_message", return_value=True)
def test_accept_cube_message_enqueues_request(mock_enqueue, mock_log_request):
    result = accept_cube_message(
        {
            "richnotificationmessage": {
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": "c1",
                        "username": "tester",
                    }
                },
                "process": {"processdata": "hello"},
            }
        }
    )

    assert result.user_id == "u1"
    assert result.message_id == "m1"
    assert result.status == "accepted"
    mock_enqueue.assert_called_once()
    mock_log_request.assert_called_once()


@patch("api.cube.service.log_request")
@patch("api.cube.service.enqueue_incoming_message", return_value=False)
def test_accept_cube_message_marks_duplicate(mock_enqueue, mock_log_request):
    result = accept_cube_message(
        {
            "user_id": "u1",
            "user_name": "tester",
            "channel": "c1",
            "message_id": "m1",
            "message": "hello",
        }
    )

    assert result.status == "duplicate"
    mock_enqueue.assert_called_once()
    mock_log_request.assert_called_once()


@patch("api.cube.service.enqueue_incoming_message", side_effect=CubeQueueError("redis down"))
def test_accept_cube_message_raises_when_queue_unavailable(mock_enqueue):
    with pytest.raises(CubeQueueUnavailableError, match="Cube message queue is unavailable."):
        accept_cube_message(
            {
                "user_id": "u1",
                "user_name": "tester",
                "channel": "c1",
                "message_id": "m1",
                "message": "hello",
            }
        )

    mock_enqueue.assert_called_once()


@patch("api.cube.service.enqueue_incoming_message")
def test_accept_cube_wakeup_message_is_ignored(mock_enqueue):
    result = accept_cube_message(
        {
            "user_id": "u1",
            "user_name": "tester",
            "channel": "c1",
            "message_id": "-1",
            "message": "!@#wake up",
        }
    )

    assert result.status == "ignored"
    mock_enqueue.assert_not_called()


@patch("api.cube.service.enqueue_incoming_message")
def test_accept_cube_empty_event_is_ignored(mock_enqueue):
    result = accept_cube_message(
        {
            "richnotificationmessage": {
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": "c1",
                        "username": "tester",
                    }
                },
                "process": {},
            }
        }
    )

    assert result.status == "ignored"
    assert result.message_id == "m1"
    mock_enqueue.assert_not_called()


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.generate_reply", return_value="nice to meet you")
@patch("api.cube.service.append_message")
@patch("api.cube.service.get_history", return_value=[{"role": "assistant", "content": "previous"}])
def test_handle_cube_message_success(
    mock_get_history,
    mock_append_message,
    mock_generate_reply,
    mock_send_multimessage,
    mock_log_request,
):
    result = handle_cube_message(
        {
            "richnotificationmessage": {
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": "c1",
                        "username": "tester",
                    }
                },
                "process": {"processdata": "hello"},
            }
        }
    )

    assert result.user_id == "u1"
    assert result.channel_id == "c1"
    assert result.message_id == "m1"
    assert result.user_message == "hello"
    assert result.llm_reply == "nice to meet you"
    mock_get_history.assert_called_once_with("u1")
    mock_generate_reply.assert_called_once_with(
        history=[{"role": "assistant", "content": "previous"}],
        user_message="hello",
    )
    assert mock_append_message.call_args_list == [
        call("u1", {"role": "user", "content": "hello"}),
        call("u1", {"role": "assistant", "content": "nice to meet you"}),
    ]
    assert mock_send_multimessage.call_count == 2
    mock_send_multimessage.assert_any_call(
        user_id="u1",
        reply_message=config.LLM_THINKING_MESSAGE,
    )
    mock_send_multimessage.assert_any_call(
        user_id="u1",
        reply_message="nice to meet you",
    )
    assert mock_log_request.call_count == 2


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.generate_reply")
@patch("api.cube.service.append_message")
def test_handle_cube_message_raises_when_message_missing(
    mock_append_message,
    mock_generate_reply,
    mock_send_multimessage,
):
    with pytest.raises(CubePayloadError, match="No message provided"):
        handle_cube_message(
            {
                "richnotificationmessage": {
                    "header": {
                        "from": {
                            "uniquename": "u1",
                            "messageid": "m1",
                            "channelid": "c1",
                            "username": "tester",
                        }
                    },
                    "process": {},
                }
            }
        )

    mock_append_message.assert_not_called()
    mock_generate_reply.assert_not_called()
    mock_send_multimessage.assert_not_called()


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.generate_reply")
@patch("api.cube.service.append_message")
@patch("api.cube.service.get_history", return_value=[])
def test_handle_cube_message_raises_when_llm_fails(
    mock_get_history,
    mock_append_message,
    mock_generate_reply,
    mock_send_multimessage,
):
    from api.llm import LLMServiceError

    mock_generate_reply.side_effect = LLMServiceError("connection refused")

    with pytest.raises(CubeUpstreamError, match="LLM reply generation failed."):
        handle_cube_message(
            {
                "richnotificationmessage": {
                    "header": {
                        "from": {
                            "uniquename": "u1",
                            "messageid": "m1",
                            "channelid": "c1",
                            "username": "tester",
                        }
                    },
                    "process": {"processdata": "hello"},
                }
            }
        )

    mock_get_history.assert_called_once_with("u1")
    mock_append_message.assert_called_once_with("u1", {"role": "user", "content": "hello"})
    # thinking message is sent before LLM call, so it should still be called once
    mock_send_multimessage.assert_called_once_with(
        user_id="u1",
        reply_message=config.LLM_THINKING_MESSAGE,
    )
