from api import config
from api.cube import rich_blocks
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


def test_build_richnotification_payload_accepts_structured_content(monkeypatch):
    monkeypatch.setattr(config, "CUBE_BOT_ID", "bot-1")
    monkeypatch.setattr(config, "CUBE_BOT_TOKEN", "token-1")
    monkeypatch.setattr(config, "CUBE_BOT_USERNAMES", ("ITC OSS", "ITC OSS"))

    content_item = rich_blocks.add_container(rich_blocks.add_table(["A"], [["1"]]))
    payload = build_richnotification_payload(
        user_id="u1",
        channel_id="c1",
        content_items=[content_item],
    )

    rich = payload["richnotification"]
    assert rich["header"]["from"] == "bot-1"
    assert rich["header"]["fromusername"] == ["ITC OSS", "ITC OSS", "", "", ""]
    assert rich["content"] == [content_item]
    assert rich["result"] == ""
