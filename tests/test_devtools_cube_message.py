import httpx

from devtools.cube_message.common import CubeMessageConfig
from devtools.cube_message.multimessage import build_multimessage_payload, send_multimessage
from devtools.cube_message.richnotification import (
    blocks,
    build_richnotification_payload,
    send_richnotification,
    send_richnotification_blocks,
)


def _config() -> CubeMessageConfig:
    return CubeMessageConfig(
        api_id="api-id",
        api_token="api-token",
        api_url="https://cube.example.com",
        multimessage_url="https://cube.example.com/api/multiMessage",
        richnotification_url="https://cube.example.com/legacy/richnotification",
        bot_id="bot-id",
        bot_token="bot-token",
        bot_usernames=("Bot",),
        richnotification_callback_url="https://app.example.com/callback",
        timeout_seconds=3,
    )


def _response(*, text: str = "accepted") -> httpx.Response:
    return httpx.Response(
        200,
        text=text,
        request=httpx.Request("POST", "https://cube.example.com/api"),
    )


def test_standalone_multimessage_builds_api_compatible_payload():
    payload = build_multimessage_payload(user_id="u1", reply_message="hello", config=_config())

    assert payload == {
        "uniqueName": "api-id",
        "token": "api-token",
        "uniqueNameList": ["u1"],
        "channelList": [],
        "msg": "hello",
    }


def test_standalone_multimessage_sends_without_api_config(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.common.httpx.post",
        return_value=_response(),
    )

    result = send_multimessage(user_id="u1", reply_message="hello", config=_config())

    assert result == {"raw": "accepted"}
    assert mock_post.call_args.kwargs["json"]["uniqueName"] == "api-id"
    assert mock_post.call_args.kwargs["timeout"] == 3


def test_standalone_richnotification_builds_api_compatible_text_payload():
    payload = build_richnotification_payload(
        user_id="u1",
        channel_id="c1",
        reply_message="hello",
        config=_config(),
    )

    assert payload == {
        "richnotification": {
            "header": {
                "from": "bot-id",
                "token": "bot-token",
                "fromusername": ["Bot"],
                "to": {
                    "uniquename": ["u1"],
                    "channelid": ["c1"],
                },
            },
            "content": {"text": "hello"},
            "result": {"status": "success", "message": "hello"},
        }
    }


def test_standalone_richnotification_sends_without_api_config(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.common.httpx.post",
        return_value=_response(),
    )

    result = send_richnotification(user_id="u1", channel_id="c1", reply_message="hello", config=_config())

    assert result == {"raw": "accepted"}
    payload = mock_post.call_args.kwargs["json"]
    assert payload["richnotification"]["header"]["from"] == "bot-id"
    assert mock_post.call_args.args[0] == "https://cube.example.com/legacy/richnotification"


def test_standalone_richnotification_blocks_adds_callback_for_request_blocks(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.common.httpx.post",
        return_value=_response(),
    )

    send_richnotification_blocks(
        blocks.add_select("Kind", [("A", "a")], processid="SelectKind"),
        user_id="u1",
        channel_id="c1",
        config=_config(),
    )

    process = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["process"]
    assert process["callbacktype"] == "url"
    assert process["callbackaddress"] == "https://app.example.com/callback"
    assert process["requestid"][:2] == ["SelectKind", "cubeuniquename"]


def test_standalone_richnotification_blocks_supports_table_and_hyperlink(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.common.httpx.post",
        return_value=_response(),
    )

    table = blocks.add_table(
        ["Name", "Link"],
        [["Docs", blocks.make_hypertext_cell("Open", "https://example.com")]],
    )

    send_richnotification_blocks(table, user_id="u1", channel_id="c1", config=_config())

    content = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]
    assert content["body"]["bodystyle"] == "grid"
    assert content["body"]["row"][1]["column"][1]["type"] == "hypertext"
    assert content["body"]["row"][1]["column"][1]["control"]["linkurl"] == "https://example.com"
