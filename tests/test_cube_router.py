from unittest.mock import patch

from api.cube.router import _extract_cube_request_fields, log_request


def test_receive_cube_missing_message(client):
    resp = client.post(
        "/api/v1/cube/receiver",
        json={
            "richnotificationmessage": {
                "header": {"from": {"uniquename": "u1", "messageid": "m1", "channelid": "c1", "username": "유저"}},
                "process": {},
            }
        },
    )
    assert resp.status_code == 400


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
                    "username": "홍길동",
                }
            },
            "process": {"processdata": "안녕하세요"},
        }
    }

    assert _extract_cube_request_fields(payload) == {
        "user_id": "u1",
        "message_id": "m1",
        "channel_id": "c1",
        "user_name": "홍길동",
        "message": "안녕하세요",
    }


@patch("api.cube.router.log_request")
@patch("api.cube.router.append_message")
def test_receive_cube_valid(
    mock_append,
    mock_log_request,
    client,
):
    resp = client.post(
        "/api/v1/cube/receiver",
        json={
            "richnotificationmessage": {
                "header": {
                    "from": {
                        "uniquename": "u1",
                        "messageid": "m1",
                        "channelid": "c1",
                        "username": "홍길동",
                    }
                },
                "process": {"processdata": "Hi"},
            }
        },
    )

    assert resp.status_code == 202
    assert resp.get_json() == {"status": "accepted", "message_id": "m1"}
    mock_append.assert_called_once_with("u1", {"role": "user", "content": "Hi"})
    mock_log_request.assert_called_once_with(
        {
            "user_id": "u1",
            "user_name": "홍길동",
            "channel_id": "c1",
            "message_id": "m1",
            "user_message": "Hi",
            "status": "accepted",
            "processor": "external",
        }
    )


def test_log_request_keeps_korean_in_log_output(caplog):
    with caplog.at_level("INFO"):
        log_request({"user_name": "홍길동", "message": "안녕하세요"})

    assert "홍길동" in caplog.text
    assert "안녕하세요" in caplog.text
    assert "\\ud64d" not in caplog.text
