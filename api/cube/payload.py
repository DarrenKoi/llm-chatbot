"""Cube 메시지 페이로드 파싱 및 응답 페이로드 빌더."""

from __future__ import annotations

from typing import Any

from api import config


def extract_user_id(payload: object) -> str | None:
    """페이로드에서 사용자 ID를 추출한다.

    Cube의 richnotificationmessage 구조와 일반 웹 요청의
    평탄한 구조를 모두 지원한다.
    """
    if not isinstance(payload, dict):
        return None

    user_id = payload.get("user_id") or payload.get("user")
    if user_id:
        return str(user_id)

    rich_message = payload.get("richnotificationmessage")
    if not isinstance(rich_message, dict):
        return None

    header = rich_message.get("header")
    if not isinstance(header, dict):
        return None

    sender = header.get("from")
    if not isinstance(sender, dict):
        return None

    nested_user_id = sender.get("uniquename")
    if not nested_user_id:
        return None
    return str(nested_user_id)


def extract_cube_request_fields(payload: dict[str, Any]) -> dict[str, str | None] | None:
    user_id = extract_user_id(payload) or "unknown"

    rich_message = payload.get("richnotificationmessage")
    if isinstance(rich_message, dict):
        header = rich_message.get("header")
        process = rich_message.get("process")
        sender = header.get("from") if isinstance(header, dict) else None
        if not isinstance(sender, dict) or not isinstance(process, dict):
            return None
        return {
            "user_id": user_id,
            "message_id": str(sender.get("messageid") or ""),
            "channel_id": str(sender.get("channelid") or ""),
            "user_name": str(sender.get("username") or ""),
            "message": process.get("processdata"),
        }

    return {
        "user_id": user_id,
        "message_id": str(payload.get("message_id") or ""),
        "channel_id": str(payload.get("channel") or ""),
        "user_name": str(payload.get("user_name") or ""),
        "message": payload.get("message"),
    }


def build_richnotification_content(reply_message: str) -> dict[str, str]:
    return {"text": reply_message}


def build_richnotification_result(reply_message: str) -> dict[str, str]:
    return {
        "status": "success",
        "message": reply_message,
    }


def build_richnotification_payload(*, user_id: str, channel_id: str, reply_message: str) -> dict[str, Any]:
    return {
        "richnotification": {
            "header": {
                "from": config.CUBE_BOT_ID,
                "token": config.CUBE_BOT_TOKEN,
                "fromusername": list(config.CUBE_BOT_USERNAMES),
                "to": {
                    "uniquename": [user_id],
                    "channelid": [channel_id],
                },
            },
            "content": build_richnotification_content(reply_message),
            "result": build_richnotification_result(reply_message),
        }
    }
