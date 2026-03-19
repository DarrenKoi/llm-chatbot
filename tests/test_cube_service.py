from unittest.mock import call, patch

import pytest

from api.cube.service import CubePayloadError, CubeUpstreamError, handle_cube_message


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.generate_reply", return_value="반갑습니다")
@patch("api.cube.service.append_message")
@patch("api.cube.service.get_history", return_value=[{"role": "assistant", "content": "이전 답변"}])
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
                        "username": "홍길동",
                    }
                },
                "process": {"processdata": "안녕하세요"},
            }
        }
    )

    assert result.user_id == "u1"
    assert result.channel_id == "c1"
    assert result.message_id == "m1"
    assert result.user_message == "안녕하세요"
    assert result.llm_reply == "반갑습니다"
    mock_get_history.assert_called_once_with("u1")
    mock_generate_reply.assert_called_once_with(
        history=[{"role": "assistant", "content": "이전 답변"}],
        user_message="안녕하세요",
    )
    assert mock_append_message.call_args_list == [
        call("u1", {"role": "user", "content": "안녕하세요"}),
        call("u1", {"role": "assistant", "content": "반갑습니다"}),
    ]
    mock_send_multimessage.assert_called_once_with(
        user_id="u1",
        reply_message="반갑습니다",
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
                            "username": "홍길동",
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
                            "username": "홍길동",
                        }
                    },
                    "process": {"processdata": "안녕하세요"},
                }
            }
        )

    mock_get_history.assert_called_once_with("u1")
    mock_append_message.assert_called_once_with("u1", {"role": "user", "content": "안녕하세요"})
    mock_send_multimessage.assert_not_called()


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.generate_reply")
@patch("api.cube.service.append_message")
@patch("api.cube.service.get_history")
def test_wakeup_message_skips_history_and_llm(
    mock_get_history,
    mock_append_message,
    mock_generate_reply,
    mock_send_multimessage,
):
    result = handle_cube_message(
        {
            "user_id": "u1",
            "user_name": "홍길동",
            "channel_id": "c1",
            "message_id": "-1",
            "message": "!@#Hello 안녕하세요",
        }
    )

    assert result.user_id == "u1"
    assert result.message_id == "-1"
    assert result.llm_reply == ""
    mock_get_history.assert_not_called()
    mock_append_message.assert_not_called()
    mock_generate_reply.assert_not_called()
    mock_send_multimessage.assert_not_called()
