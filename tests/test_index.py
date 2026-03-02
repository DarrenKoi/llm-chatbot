import json
from unittest.mock import patch, MagicMock

from index import _extract_image_url


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_receive_cube_missing_message(client):
    resp = client.post(
        "/api/v1/receive/cube",
        json={"user_id": "u1", "channel_id": "c1"},
    )
    assert resp.status_code == 400


@patch("index.send_rich_notification")
@patch("index.log_request")
@patch("index.chat")
@patch("index.append_messages")
@patch("index.append_message")
@patch("index.get_history", return_value=[])
def test_receive_cube_valid(
    mock_get_hist, mock_append, mock_append_multi,
    mock_chat, mock_log, mock_send, client,
):
    mock_chat.return_value = ("Hello!", [{"role": "assistant", "content": "Hello!"}], {"llm_calls": [], "tool_executions": []})

    # Run synchronously by replacing executor.submit with direct call
    with patch("index.executor") as mock_executor:
        mock_executor.submit.side_effect = lambda fn, *args: fn(*args)
        resp = client.post(
            "/api/v1/receive/cube",
            json={"user_id": "u1", "channel_id": "c1", "message": "Hi"},
        )

    assert resp.status_code == 202
    mock_get_hist.assert_called_once_with("u1")
    mock_append.assert_called_once()
    mock_chat.assert_called_once()
    mock_send.assert_called_once_with("c1", "Hello!", image_url=None)
    mock_log.assert_called_once()


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
