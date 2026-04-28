import logging
import time
from unittest.mock import call, patch

import pytest

from api import config
from api.cube import service as cube_service
from api.cube.intents import ChoiceIntent, ChoiceOption, TableIntent, TextIntent
from api.cube.queue import CubeQueueError
from api.cube.service import (
    CubePayloadError,
    CubeQueueUnavailableError,
    CubeUpstreamError,
    accept_cube_message,
    handle_cube_message,
)
from api.workflows.models import WorkflowReply


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
@patch("api.cube.service.enqueue_incoming_message", return_value=True)
def test_accept_cube_message_enqueues_richnotification_callback(mock_enqueue, mock_log_request):
    result = accept_cube_message(
        {
            "result": {
                "resultdata": [
                    {
                        "requestid": "Survey",
                        "value": ["after"],
                        "text": ["식후"],
                    },
                    {
                        "requestid": "Comment",
                        "value": ["메모"],
                        "text": ["메모"],
                    },
                ]
            },
            "header": {
                "from": {
                    "uniquename": "u1",
                    "messageid": "m1",
                    "channelid": 505912193,
                    "username": "tester",
                }
            },
            "process": {"processdata": "", "session": {"sequence": "1", "sessionid": "CubeBot"}},
        }
    )

    assert result.user_id == "u1"
    assert result.message_id.startswith("m1:callback:")
    assert result.status == "accepted"
    incoming = mock_enqueue.call_args.args[0]
    assert incoming.user_id == "u1"
    assert incoming.channel_id == "505912193"
    assert incoming.message == "Survey: 식후 (after)\nComment: 메모"
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
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(reply="nice to meet you", workflow_id="start_chat"),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_success(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_multimessage,
    mock_log_request,
    caplog,
):
    caplog.set_level(logging.INFO, logger="api.cube.service")

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
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
    assert mock_handle_workflow_message.call_count == 1
    incoming = mock_handle_workflow_message.call_args.args[0]
    assert incoming.user_id == "u1"
    assert incoming.message == "hello"
    assert mock_handle_workflow_message.call_args.kwargs["attempt"] == 0
    assert mock_append_message.call_args_list == [
        call(
            "u1",
            {"role": "user", "content": "hello"},
            conversation_id="c1",
            metadata={
                "channel_id": "c1",
                "source": "cube",
                "direction": "inbound",
                "user_name": "tester",
                "message_id": "m1",
            },
        ),
        call(
            "u1",
            {"role": "assistant", "content": "nice to meet you"},
            conversation_id="c1",
            metadata={
                "channel_id": "c1",
                "source": "cube",
                "direction": "outbound",
                "user_name": "tester",
                "reply_to_message_id": "m1",
                "workflow_id": "start_chat",
            },
        ),
    ]
    mock_send_multimessage.assert_called_once_with(
        user_id="u1",
        reply_message="nice to meet you",
    )
    assert mock_log_request.call_count == 2
    assert "Workflow handling scheduled" in caplog.text


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_richnotification")
@patch("api.cube.service.send_richnotification_blocks")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(reply="| 이름 | 값 |\n|---|---|\n| A | 1 |", workflow_id="start_chat"),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_sends_markdown_table_as_structured_richnotification(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_richnotification_blocks,
    mock_send_richnotification,
    mock_log_request,
):
    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        with patch.object(config, "CUBE_RICH_ROUTING_ENABLED", True):
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

    assert result.llm_reply == "| 이름 | 값 |\n|---|---|\n| A | 1 |"
    mock_send_richnotification.assert_not_called()
    mock_send_richnotification_blocks.assert_called_once()
    block = mock_send_richnotification_blocks.call_args.args[0]
    assert block.bodystyle == "grid"
    assert block.rows[0]["column"][0]["control"]["text"][0] == "이름"
    assert block.rows[1]["column"][1]["control"]["text"][0] == "1"
    assert mock_handle_workflow_message.call_count == 1
    assert mock_append_message.call_count == 2
    assert mock_log_request.call_count == 2


@patch("api.cube.service.send_richnotification")
@patch("api.cube.service.send_richnotification_blocks")
def test_send_rich_delivery_item_falls_back_when_table_parse_fails(
    mock_send_richnotification_blocks,
    mock_send_richnotification,
):
    cube_service._send_rich_delivery_item(user_id="u1", channel_id="c1", kind="table", content="not a table")

    mock_send_richnotification_blocks.assert_not_called()
    mock_send_richnotification.assert_called_once_with(
        user_id="u1",
        channel_id="c1",
        reply_message="not a table",
    )


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(reply="처리했습니다.", workflow_id="start_chat"),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_richnotification_callback_success(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_multimessage,
    mock_log_request,
):
    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        result = handle_cube_message(
            {
                "result": {
                    "resultdata": [
                        {
                            "requestid": "Survey",
                            "value": ["after"],
                            "text": ["식후"],
                        },
                        {
                            "requestid": "Comment",
                            "value": ["메모"],
                            "text": ["메모"],
                        },
                    ]
                },
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": 505912193,
                        "username": "tester",
                    }
                },
                "process": {"processdata": "", "session": {"sequence": "1", "sessionid": "CubeBot"}},
            }
        )

    assert result.user_id == "u1"
    assert result.channel_id == "505912193"
    assert result.message_id.startswith("m1:callback:")
    assert result.user_message == "Survey: 식후 (after)\nComment: 메모"
    incoming = mock_handle_workflow_message.call_args.args[0]
    assert incoming.channel_id == "505912193"
    assert incoming.message == "Survey: 식후 (after)\nComment: 메모"
    assert mock_append_message.call_args_list == [
        call(
            "u1",
            {"role": "user", "content": "Survey: 식후 (after)\nComment: 메모"},
            conversation_id="505912193",
            metadata={
                "channel_id": "505912193",
                "source": "cube",
                "direction": "inbound",
                "user_name": "tester",
                "message_id": result.message_id,
            },
        ),
        call(
            "u1",
            {"role": "assistant", "content": "처리했습니다."},
            conversation_id="505912193",
            metadata={
                "channel_id": "505912193",
                "source": "cube",
                "direction": "outbound",
                "user_name": "tester",
                "reply_to_message_id": result.message_id,
                "workflow_id": "start_chat",
            },
        ),
    ]
    mock_send_multimessage.assert_called_once_with(
        user_id="u1",
        reply_message="처리했습니다.",
    )
    assert mock_log_request.call_count == 2


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.append_message")
def test_handle_cube_message_sends_thinking_message_only_when_reply_is_slow(
    mock_append_message,
    mock_send_multimessage,
    mock_log_request,
    caplog,
):
    caplog.set_level(logging.INFO, logger="api.cube.service")

    def slow_reply(*args, **kwargs):
        time.sleep(0.2)
        return WorkflowReply(reply="nice to meet you", workflow_id="start_chat")

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 0.01):
        with patch("api.cube.service.handle_workflow_message", side_effect=slow_reply) as mock_handle_workflow_message:
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
    assert result.llm_reply == "nice to meet you"
    assert mock_handle_workflow_message.call_count == 1
    assert mock_append_message.call_args_list == [
        call(
            "u1",
            {"role": "user", "content": "hello"},
            conversation_id="c1",
            metadata={
                "channel_id": "c1",
                "source": "cube",
                "direction": "inbound",
                "user_name": "tester",
                "message_id": "m1",
            },
        ),
        call(
            "u1",
            {"role": "assistant", "content": "nice to meet you"},
            conversation_id="c1",
            metadata={
                "channel_id": "c1",
                "source": "cube",
                "direction": "outbound",
                "user_name": "tester",
                "reply_to_message_id": "m1",
                "workflow_id": "start_chat",
            },
        ),
    ]
    assert mock_send_multimessage.call_count == 2
    assert mock_send_multimessage.call_args_list[0] == call(
        user_id="u1",
        reply_message=config.LLM_THINKING_MESSAGE,
    )
    assert mock_send_multimessage.call_args_list[1] == call(
        user_id="u1",
        reply_message="nice to meet you",
    )
    assert mock_log_request.call_count == 2
    assert "Workflow handling exceeded thinking delay" in caplog.text


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.handle_workflow_message")
@patch("api.cube.service.append_message")
def test_handle_cube_message_raises_when_message_missing(
    mock_append_message,
    mock_handle_workflow_message,
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
    mock_handle_workflow_message.assert_not_called()
    mock_send_multimessage.assert_not_called()


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.handle_workflow_message")
@patch("api.cube.service.append_message")
def test_handle_cube_message_raises_when_llm_fails(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_multimessage,
):
    mock_handle_workflow_message.side_effect = RuntimeError("workflow failed")

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        with pytest.raises(CubeUpstreamError, match="Workflow reply generation failed."):
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

    mock_append_message.assert_called_once_with(
        "u1",
        {"role": "user", "content": "hello"},
        conversation_id="c1",
        metadata={
            "channel_id": "c1",
            "source": "cube",
            "direction": "inbound",
            "user_name": "tester",
            "message_id": "m1",
        },
    )
    mock_send_multimessage.assert_not_called()


@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.append_message")
def test_handle_cube_message_sends_thinking_message_when_slow_reply_then_fails(
    mock_append_message,
    mock_send_multimessage,
):
    def slow_failure(*args, **kwargs):
        time.sleep(0.05)
        raise RuntimeError("workflow failed")

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 0.01):
        with patch("api.cube.service.handle_workflow_message", side_effect=slow_failure):
            with pytest.raises(CubeUpstreamError, match="Workflow reply generation failed."):
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

    mock_append_message.assert_called_once_with(
        "u1",
        {"role": "user", "content": "hello"},
        conversation_id="c1",
        metadata={
            "channel_id": "c1",
            "source": "cube",
            "direction": "inbound",
            "user_name": "tester",
            "message_id": "m1",
        },
    )
    mock_send_multimessage.assert_called_once_with(
        user_id="u1",
        reply_message=config.LLM_THINKING_MESSAGE,
    )


# --- Intent-driven richnotification routing ----------------------------------


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.send_richnotification")
@patch("api.cube.service.send_richnotification_blocks")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(
        reply="형식을 골라주세요.",
        workflow_id="start_chat",
        intents=[
            TextIntent(text="형식을 골라주세요."),
            ChoiceIntent(
                question="형식",
                options=[ChoiceOption(label="PDF", value="pdf"), ChoiceOption(label="엑셀", value="xlsx")],
                processid="SelectFormat",
            ),
        ],
    ),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_routes_structured_intents_to_blocks(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_richnotification_blocks,
    mock_send_richnotification,
    mock_send_multimessage,
    mock_log_request,
):
    delivery_order = []
    mock_send_multimessage.side_effect = lambda **kwargs: delivery_order.append(("multi", kwargs["reply_message"]))
    mock_send_richnotification_blocks.side_effect = lambda *args, **kwargs: delivery_order.append(("rich", len(args)))

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        with patch.object(config, "CUBE_DELIVERY_DELAY_SECONDS", 1.0):
            with patch(
                "api.cube.service.time.sleep",
                side_effect=lambda delay: delivery_order.append(("sleep", delay)),
            ):
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
                            "process": {"processdata": "PDF로 받을까요 엑셀로 받을까요?"},
                        }
                    }
                )

    assert delivery_order == [("multi", "형식을 골라주세요."), ("sleep", 1.0), ("rich", 1)]
    mock_send_multimessage.assert_called_once_with(user_id="u1", reply_message="형식을 골라주세요.")
    mock_send_richnotification.assert_not_called()
    mock_send_richnotification_blocks.assert_called_once()
    sent_blocks = mock_send_richnotification_blocks.call_args.args
    assert len(sent_blocks) == 1
    radio_cell_types = {col["type"] for row in sent_blocks[0].rows for col in row["column"]}
    assert "radio" in radio_cell_types


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.send_richnotification")
@patch("api.cube.service.send_richnotification_blocks")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(
        reply="요약\n\n[표] 헤더: 이름 (1행)\n\n마무리",
        workflow_id="start_chat",
        intents=[
            TextIntent(text="요약"),
            TableIntent(headers=["이름"], rows=[["A"]]),
            TextIntent(text="마무리"),
        ],
    ),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_preserves_mixed_intent_delivery_order(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_richnotification_blocks,
    mock_send_richnotification,
    mock_send_multimessage,
    mock_log_request,
):
    delivery_order = []
    mock_send_multimessage.side_effect = lambda **kwargs: delivery_order.append(("multi", kwargs["reply_message"]))
    mock_send_richnotification_blocks.side_effect = lambda *args, **kwargs: delivery_order.append(("rich", len(args)))

    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        with patch.object(config, "CUBE_DELIVERY_DELAY_SECONDS", 1.0):
            with patch(
                "api.cube.service.time.sleep",
                side_effect=lambda delay: delivery_order.append(("sleep", delay)),
            ):
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
                            "process": {"processdata": "순서 확인"},
                        }
                    }
                )

    assert delivery_order == [
        ("multi", "요약"),
        ("sleep", 1.0),
        ("rich", 1),
        ("sleep", 1.0),
        ("multi", "마무리"),
    ]
    assert mock_send_multimessage.call_args_list == [
        call(user_id="u1", reply_message="요약"),
        call(user_id="u1", reply_message="마무리"),
    ]
    mock_send_richnotification.assert_not_called()
    mock_send_richnotification_blocks.assert_called_once()
    table_block = mock_send_richnotification_blocks.call_args.args[0]
    assert table_block.bodystyle == "grid"


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.send_richnotification_blocks")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(
        reply="| 이름 | 값 |\n|---|---|\n| A | 1 |",
        workflow_id="start_chat",
        intents=[TextIntent(text="| 이름 | 값 |\n|---|---|\n| A | 1 |")],
    ),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_text_intent_stays_multimessage_even_when_rich_routing_enabled(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_richnotification_blocks,
    mock_send_multimessage,
    mock_log_request,
):
    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
        with patch.object(config, "CUBE_RICH_ROUTING_ENABLED", True):
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
                        "process": {"processdata": "표를 텍스트로 보여줘"},
                    }
                }
            )

    mock_send_richnotification_blocks.assert_not_called()
    mock_send_multimessage.assert_called_once_with(user_id="u1", reply_message="| 이름 | 값 |\n|---|---|\n| A | 1 |")


@patch("api.cube.service.log_request")
@patch("api.cube.service.send_multimessage")
@patch("api.cube.service.send_richnotification_blocks")
@patch(
    "api.cube.service.handle_workflow_message",
    return_value=WorkflowReply(
        reply="안녕하세요",
        workflow_id="start_chat",
        intents=[TextIntent(text="안녕하세요")],
    ),
)
@patch("api.cube.service.append_message")
def test_handle_cube_message_text_only_intents_use_chunker_path(
    mock_append_message,
    mock_handle_workflow_message,
    mock_send_richnotification_blocks,
    mock_send_multimessage,
    mock_log_request,
):
    with patch.object(config, "LLM_THINKING_MESSAGE_DELAY_SECONDS", 1.0):
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
                    "process": {"processdata": "안녕"},
                }
            }
        )

    mock_send_richnotification_blocks.assert_not_called()
    mock_send_multimessage.assert_called_once_with(user_id="u1", reply_message="안녕하세요")
