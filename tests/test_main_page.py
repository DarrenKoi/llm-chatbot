from unittest.mock import patch


def test_main_page_renders_main_template(client):
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


@patch("api.file_delivery.router.list_files_for_user", return_value=[])
def test_file_delivery_page_renders_upload_ui_for_cookie_user(mock_list_files_for_user, client):
    client.set_cookie("LASTUSER", "cube.user")

    response = client.get("/file_delivery")

    assert response.status_code == 200
    assert b"Upload And Get URL" in response.data
    assert b"cube.user" in response.data
    mock_list_files_for_user.assert_called_once_with(user_id="cube.user", limit=20)


def test_workflow_graph_page_uses_wide_layout(client):
    response = client.get("/workflows/translator")

    assert response.status_code == 200
    assert b"Workflow: translator" in response.data
    assert b"width: min(80vw, 1500px);" in response.data
    assert b"height: min(78vh, 920px) !important;" in response.data
