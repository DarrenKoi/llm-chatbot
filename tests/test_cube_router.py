from unittest.mock import patch

from api.cube.models import CubeAcceptedMessage
from api.cube.router import _extract_cube_request_fields, log_request


def test_receive_cube_missing_message(client):
    resp = client.post(
        "/api/v1/cube/receiver",
        json={
            "richnotificationmessage": {
                "header": {"from": {"uniquename": "u1", "messageid": "m1", "channelid": "c1", "username": "user"}},
                "process": {},
            }
        },
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ignored", "message_id": "m1"}


def test_receive_cube_invalid_payload(client):
    resp = client.post("/api/v1/cube/receiver", data="not-json", content_type="text/plain")
    assert resp.status_code == 400


def test_extract_cube_request_fields_from_rich_notification_message():
    payload = {
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

    assert _extract_cube_request_fields(payload) == {
        "user_id": "u1",
        "message_id": "m1",
        "channel_id": "c1",
        "user_name": "tester",
        "message": "hello",
    }


@patch("api.cube.router.accept_cube_message")
def test_receive_cube_valid(mock_accept_cube_message, client):
    mock_accept_cube_message.return_value = CubeAcceptedMessage(
        user_id="u1",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        status="accepted",
    )

    resp = client.post(
        "/api/v1/cube/receiver",
        json={
            "richnotificationmessage": {
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": "c1",
                        "username": "tester",
                    }
                },
                "process": {"processdata": "Hi"},
            }
        },
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "accepted", "message_id": "m1"}
    mock_accept_cube_message.assert_called_once()


@patch("api.cube.router.accept_cube_message")
def test_receive_cube_duplicate(mock_accept_cube_message, client):
    mock_accept_cube_message.return_value = CubeAcceptedMessage(
        user_id="u1",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        status="duplicate",
    )

    resp = client.post(
        "/api/v1/cube/receiver",
        json={"message": "Hi", "user_id": "u1", "channel": "c1", "message_id": "m1"},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "duplicate", "message_id": "m1"}


@patch("api.cube.router.accept_cube_message")
def test_receive_cube_queue_failure(mock_accept_cube_message, client):
    from api.cube.service import CubeQueueUnavailableError

    mock_accept_cube_message.side_effect = CubeQueueUnavailableError("Cube message queue is unavailable.")

    resp = client.post(
        "/api/v1/cube/receiver",
        json={"message": "Hi", "user_id": "u1", "channel": "c1"},
    )

    assert resp.status_code == 503
    assert resp.get_json() == {"error": "Cube message queue is unavailable."}


def test_log_request_keeps_korean_in_log_output(caplog):
    with caplog.at_level("INFO"):
        log_request({"user_name": "홍길동", "message": "안녕하세요"})

    assert "홍길동" in caplog.text
    assert "안녕하세요" in caplog.text
    assert "\\ud64d" not in caplog.text
