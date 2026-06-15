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


def test_extract_cube_request_fields_from_rich_notification_callback():
    payload = {
        "result": {
            "resultdata": [
                {
                    "requestid": "Survey",
                    "value": ["after"],
                    "text": ["식후"],
                },
                {
                    "requestid": "SelectDate",
                    "value": ["2026-04-25"],
                    "text": ["2026-04-25"],
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
        "process": {
            "processdata": "",
            "session": {"sequence": "1", "sessionid": "CubeBot"},
        },
    }

    fields = _extract_cube_request_fields(payload)

    assert fields is not None
    assert fields["user_id"] == "u1"
    assert fields["channel_id"] == "505912193"
    assert fields["user_name"] == "tester"
    assert fields["message"] == "Survey: 식후 (after)\nSelectDate: 2026-04-25\nComment: 메모"
    assert str(fields["message_id"]).startswith("m1:callback:")


def test_extract_cube_request_fields_from_wrapped_callback_with_empty_processdata():
    """'자세히 보기' 등 후속 버튼 콜백: richnotificationmessage 래퍼 안에
    processdata는 비어 있고 응답이 result.resultdata에 담겨 온다."""
    payload = {
        "richnotificationmessage": {
            "header": {
                "from": {
                    "uniquename": "u1",
                    "messageid": "m2",
                    "channelid": 505912193,
                    "username": "tester",
                }
            },
            "process": {"processdata": ""},
            "result": {
                "resultdata": [
                    {"requestid": "Detail", "value": ["view"], "text": ["자세히 보기"]},
                ]
            },
        }
    }

    fields = _extract_cube_request_fields(payload)

    assert fields is not None
    assert fields["user_id"] == "u1"
    assert fields["channel_id"] == "505912193"
    assert fields["user_name"] == "tester"
    # processdata가 비어 있어도 resultdata에서 메시지를 추출해야 한다.
    assert fields["message"] == "Detail: 자세히 보기 (view)"
    # messageid가 클릭마다 고유하므로 그대로 사용한다(콜백 해시 합성 X).
    assert fields["message_id"] == "m2"


def test_extract_cube_request_fields_wrapped_processdata_unchanged():
    """processdata에 텍스트가 있는 일반 메시지는 기존 동작을 유지한다."""
    payload = {
        "richnotificationmessage": {
            "header": {"from": {"uniquename": "u1", "messageid": "m1", "channelid": "c1", "username": "tester"}},
            "process": {"processdata": "안녕"},
            "result": {"resultdata": [{"requestid": "Detail", "value": ["view"], "text": ["자세히 보기"]}]},
        }
    }

    fields = _extract_cube_request_fields(payload)

    assert fields is not None
    # processdata가 있으면 resultdata보다 우선한다(폴백은 비어 있을 때만).
    assert fields["message"] == "안녕"
    assert fields["message_id"] == "m1"


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
def test_receive_cube_richnotification_callback(mock_accept_cube_message, client):
    mock_accept_cube_message.return_value = CubeAcceptedMessage(
        user_id="u1",
        user_name="tester",
        channel_id="505912193",
        message_id="m1:callback:abc123",
        status="accepted",
    )

    resp = client.post(
        "/api/v1/cube/richnotification/callback",
        json={
            "result": {
                "resultdata": [
                    {
                        "requestid": "Survey",
                        "value": ["after"],
                        "text": ["식후"],
                    }
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
        },
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"status": "accepted", "message_id": "m1:callback:abc123"}
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
