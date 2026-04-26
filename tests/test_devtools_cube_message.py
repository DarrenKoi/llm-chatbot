import httpx

from devtools.cube_message import blocks, samples
from devtools.cube_message.client import (
    CubeMessageConfig,
    send_blocks,
    send_raw_content,
    send_text,
)


def _config() -> CubeMessageConfig:
    return CubeMessageConfig(
        richnotification_url="https://cube.example.com/legacy/richnotification",
        bot_id="bot-id",
        bot_token="bot-token",
        bot_usernames=("Bot",),
        callback_url="https://app.example.com/callback",
        timeout_seconds=3,
    )


def _response(*, text: str = "accepted") -> httpx.Response:
    return httpx.Response(
        200,
        text=text,
        request=httpx.Request("POST", "https://cube.example.com/api"),
    )


def test_send_text_posts_text_block(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    result = send_text("hello", user_id="u1", channel_id="c1", config=_config())

    assert result == {"raw": "accepted"}
    payload = mock_post.call_args.kwargs["json"]
    header = payload["richnotification"]["header"]
    assert header["from"] == "bot-id"
    assert header["to"] == {"uniquename": ["u1"], "channelid": ["c1"]}
    assert mock_post.call_args.args[0] == "https://cube.example.com/legacy/richnotification"
    assert mock_post.call_args.kwargs["timeout"] == 3

    column = payload["richnotification"]["content"][0]["body"]["row"][0]["column"][0]
    assert column["type"] == "label"
    assert column["control"]["text"][0] == "hello"


def test_send_blocks_auto_attaches_callback_for_request_blocks(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    send_blocks(
        blocks.add_select("Kind", [("A", "a")], processid="SelectKind"),
        user_id="u1",
        channel_id="c1",
        config=_config(),
    )

    process = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["process"]
    assert process["callbacktype"] == "url"
    assert process["callbackaddress"] == "https://app.example.com/callback"
    assert process["requestid"][:2] == ["SelectKind", "cubeuniquename"]


def test_send_blocks_skips_callback_for_static_blocks(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    send_blocks(
        blocks.add_text("just text"),
        user_id="u1",
        channel_id="c1",
        config=_config(),
    )

    process = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["process"]
    assert process["callbacktype"] == ""
    assert process["callbackaddress"] == ""


def test_send_blocks_supports_table_with_hyperlink(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    table = blocks.add_table(
        ["Name", "Link"],
        [["Docs", blocks.make_hypertext_cell("Open", "https://example.com")]],
    )

    send_blocks(table, user_id="u1", channel_id="c1", config=_config())

    content = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]
    assert content["body"]["bodystyle"] == "grid"
    assert content["body"]["row"][1]["column"][1]["type"] == "hypertext"
    assert content["body"]["row"][1]["column"][1]["control"]["linkurl"] == "https://example.com"


def test_send_raw_content_replaces_header_and_fills_callback(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    raw = [
        {
            "header": {},
            "body": {"bodystyle": "none", "row": []},
            "process": {
                "callbacktype": "url",
                "callbackaddress": "",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {"sessionid": "", "sequence": ""},
                "mandatory": [],
                "requestid": ["SomeRequest"],
            },
        }
    ]

    send_raw_content(raw, user_id="u1", channel_id="c1", config=_config())

    payload = mock_post.call_args.kwargs["json"]["richnotification"]
    assert payload["header"]["from"] == "bot-id"
    assert payload["header"]["to"]["uniquename"] == ["u1"]
    assert payload["content"][0]["process"]["callbackaddress"] == "https://app.example.com/callback"
    assert raw[0]["process"]["callbackaddress"] == "", "원본은 변경되면 안 된다 (deepcopy 보장)"


def test_samples_list_includes_known_probes():
    available = samples.list_samples()

    assert "text_baseline" in available
    assert "approval_buttons" in available
    assert "grid_table" in available


def test_send_sample_dispatches_by_name(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("text_baseline", user_id="u1", channel_id="c1", config=_config())

    payload = mock_post.call_args.kwargs["json"]["richnotification"]
    assert payload["header"]["from"] == "bot-id"
    assert payload["content"][0]["body"]["row"][0]["column"][0]["type"] == "label"


def test_send_sample_with_buttons_attaches_callback(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("approval_buttons", user_id="u1", channel_id="c1", config=_config())

    process = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["process"]
    assert process["callbacktype"] == "url"
    assert process["callbackaddress"] == "https://app.example.com/callback"
    assert "AgreeButton" in process["requestid"]
    assert "RejectButton" in process["requestid"]


def test_send_sample_unknown_name_raises():
    import pytest

    with pytest.raises(ValueError, match="알 수 없는 샘플"):
        samples.send_sample("does_not_exist", user_id="u1", channel_id="c1", config=_config())
