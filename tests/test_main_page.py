from unittest.mock import patch


def test_main_page_renders_sample_template(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Signal Room" in response.data
    assert b"Server Status" in response.data


@patch("api.get_recent_messages", return_value=[{"user_id": "u1", "role": "user", "content": "hello"}])
def test_main_page_renders_recent_conversation(mock_get_recent_messages, client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Conversation Debug" in response.data
    assert b"hello" in response.data
    assert b"u1" in response.data
    mock_get_recent_messages.assert_called_once_with(limit=50)
