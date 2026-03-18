import json
from unittest.mock import patch

from api.cube.router import _extract_image_url


def test_receive_cube_missing_message(client):
    resp = client.post(
        "/api/v1/cube/receiver",
        json={"user": "u1", "message_id": "m1", "channel": "c1"},
    )
    assert resp.status_code == 400


def test_receive_cube_invalid_payload(client):
    resp = client.post("/api/v1/cube/receiver", data="not-json", content_type="text/plain")
    assert resp.status_code == 400


@patch("api.cube.router.send_rich_notification")
@patch("api.cube.router.chat")
@patch("api.cube.router.append_messages")
@patch("api.cube.router.append_message")
@patch("api.cube.router.get_history", return_value=[])
def test_receive_cube_valid(
    mock_get_hist,
    mock_append,
    mock_append_multi,
    mock_chat,
    mock_send,
    client,
):
    mock_chat.return_value = (
        "Hello!",
        [{"role": "assistant", "content": "Hello!"}],
        {"llm_calls": [], "tool_executions": []},
    )

    with patch("api.cube.router.executor") as mock_executor:
        mock_executor.submit.side_effect = lambda fn, *args: fn(*args)
        resp = client.post(
            "/api/v1/cube/receiver",
            json={"user": "u1", "message_id": "m1", "channel": "c1", "message": "Hi"},
        )

    assert resp.status_code == 202
    assert resp.get_json() == {"status": "accepted", "message_id": "m1"}
    mock_get_hist.assert_called_once_with("u1")
    mock_append.assert_called_once_with("u1", {"role": "user", "content": "Hi"})
    mock_append_multi.assert_called_once()
    mock_chat.assert_called_once()
    mock_send.assert_called_once_with("c1", "Hello!", image_url=None)


def test_extract_image_url_found():
    messages = [
        {"role": "assistant", "content": "Here's the chart"},
        {"role": "tool", "content": json.dumps({"image_url": "http://example.com/chart.png"})},
    ]
    assert _extract_image_url(messages) == "http://example.com/chart.png"


def test_extract_image_url_not_found():
    messages = [
        {"role": "assistant", "content": "No chart here"},
        {"role": "tool", "content": json.dumps({"result": "data"})},
    ]
    assert _extract_image_url(messages) is None


def test_extract_image_url_invalid_json():
    messages = [{"role": "tool", "content": "not json"}]
    assert _extract_image_url(messages) is None
