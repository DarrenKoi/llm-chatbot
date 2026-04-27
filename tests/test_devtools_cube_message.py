import httpx
import pytest

from devtools.cube_message import blocks, raw_richnotification_test, samples
from devtools.cube_message.client import (
    CubeMessageConfig,
    CubeMessageError,
    prepare_raw_richnotification_payload,
    send_blocks,
    send_raw_content,
    send_raw_richnotification,
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


def test_prepare_raw_richnotification_replaces_header_and_allows_empty_channel():
    raw = {
        "richnotification": {
            "header": {
                "from": "old-bot",
                "token": "old-token",
                "fromusername": ["Old Bot"],
                "to": {"uniquename": ["old-user"], "channelid": ["old-channel"]},
            },
            "content": [
                {
                    "header": {},
                    "body": {"bodystyle": "none", "row": []},
                    "process": {
                        "callbacktype": "url",
                        "callbackaddress": "",
                        "requestid": ["SomeRequest"],
                    },
                }
            ],
            "result": "",
        }
    }

    prepared = prepare_raw_richnotification_payload(
        raw,
        user_id="u1",
        channel_id="",
        config=_config(),
    )

    rich = prepared["richnotification"]
    assert rich["header"]["from"] == "bot-id"
    assert rich["header"]["token"] == "bot-token"
    assert rich["header"]["fromusername"] == ["Bot", "", "", "", ""]
    assert rich["header"]["to"] == {"uniquename": ["u1"], "channelid": [""]}
    assert rich["content"][0]["process"]["callbackaddress"] == "https://app.example.com/callback"
    assert raw["richnotification"]["header"]["from"] == "old-bot"
    assert raw["richnotification"]["content"][0]["process"]["callbackaddress"] == ""


def test_send_raw_richnotification_posts_complete_payload(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )
    raw = raw_richnotification_test.load_raw_richnotification("text_summary.json")

    send_raw_richnotification(raw, user_id="u1", channel_id="", config=_config())

    payload = mock_post.call_args.kwargs["json"]
    rich = payload["richnotification"]
    assert rich["header"]["to"] == {"uniquename": ["u1"], "channelid": [""]}
    assert rich["content"][0]["process"]["session"]["sessionid"] == "raw-rich-text-summary"
    assert raw["richnotification"]["header"]["from"] == "raw-placeholder-bot"


def test_raw_rich_test_defaults_channel_id_to_empty_string():
    assert raw_richnotification_test.CHANNEL_ID == ""


def test_raw_rich_test_send_raw_file_loads_named_example(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    raw_richnotification_test.send_raw_file("grid_table", user_id="u1", config=_config())

    rich = mock_post.call_args.kwargs["json"]["richnotification"]
    assert rich["header"]["to"]["channelid"] == [""]
    assert rich["content"][0]["body"]["bodystyle"] == "grid"


def test_prepare_raw_richnotification_requires_richnotification_object():
    with pytest.raises(CubeMessageError, match="richnotification"):
        prepare_raw_richnotification_payload({}, user_id="u1", channel_id="", config=_config())


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
    with pytest.raises(ValueError, match="알 수 없는 샘플"):
        samples.send_sample("does_not_exist", user_id="u1", channel_id="c1", config=_config())


# --- Production block probe smoke tests ----------------------------------


PROD_PROBES = [
    "buttons_basic",
    "radio_choice",
    "checkbox_choice",
    "select_dropdown",
    "input_field",
    "textarea_field",
    "datepicker_basic",
    "datetimepicker_basic",
    "image_basic",
    "mixed_form",
]


@pytest.mark.parametrize("probe", PROD_PROBES)
def test_production_probe_posts_valid_payload(mocker, probe):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample(probe, user_id="u1", channel_id="c1", config=_config())

    payload = mock_post.call_args.kwargs["json"]["richnotification"]
    assert payload["header"]["from"] == "bot-id"
    assert payload["header"]["to"]["uniquename"] == ["u1"]
    assert payload["content"], f"{probe}: content array should not be empty"
    assert payload["content"][0]["body"]["row"], f"{probe}: should have at least one row"


def test_radio_choice_uses_radio_cells_not_checkbox(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("radio_choice", user_id="u1", channel_id="c1", config=_config())

    rows = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["body"]["row"]
    cell_types = {col["type"] for row in rows for col in row["column"]}
    assert "radio" in cell_types
    assert "checkbox" not in cell_types


def test_checkbox_choice_uses_checkbox_cells(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("checkbox_choice", user_id="u1", channel_id="c1", config=_config())

    rows = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["body"]["row"]
    cell_types = {col["type"] for row in rows for col in row["column"]}
    assert "checkbox" in cell_types
    assert "radio" not in cell_types


def test_datepicker_default_value_propagates(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("datepicker_basic", user_id="u1", channel_id="c1", config=_config())

    rows = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["body"]["row"]
    datepicker_cell = next(col for row in rows for col in row["column"] if col["type"] == "datepicker")
    assert datepicker_cell["control"]["value"] == "2026/05/01"


def test_mixed_form_attaches_callback_and_aggregates_request_ids(mocker):
    mock_post = mocker.patch(
        "devtools.cube_message.client.httpx.post",
        return_value=_response(),
    )

    samples.send_sample("mixed_form", user_id="u1", channel_id="c1", config=_config())

    process = mock_post.call_args.kwargs["json"]["richnotification"]["content"][0]["process"]
    assert process["callbackaddress"] == "https://app.example.com/callback"
    for expected_pid in ("SelectRoom", "SelectDateTime", "InputCount", "SendButton"):
        assert expected_pid in process["requestid"], f"{expected_pid} missing from requestid"
