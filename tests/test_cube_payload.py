from api import config
from api.cube.payload import build_richnotification_payload


def test_build_richnotification_payload_uses_cube_config(monkeypatch):
    monkeypatch.setattr(config, "CUBE_BOT_ID", "bot-1")
    monkeypatch.setattr(config, "CUBE_BOT_TOKEN", "token-1")
    monkeypatch.setattr(config, "CUBE_BOT_USERNAMES", ("ITC OSS", "ITC OSS"))

    payload = build_richnotification_payload(
        user_id="u1",
        channel_id="c1",
        reply_message="응답입니다",
    )

    assert payload == {
        "richnotification": {
            "header": {
                "from": "bot-1",
                "token": "token-1",
                "fromusername": ["ITC OSS", "ITC OSS"],
                "to": {
                    "uniquename": ["u1"],
                    "channelid": ["c1"],
                },
            },
            "content": {"text": "응답입니다"},
            "result": {"status": "success", "message": "응답입니다"},
        }
    }
