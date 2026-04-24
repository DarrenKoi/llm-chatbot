"""Cube 메시지 페이로드 파싱 및 응답 페이로드 빌더."""

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from api import config
from api.cube import rich_blocks

_SYSTEM_RESULT_REQUEST_IDS = {
    "cubeuniquename",
    "cubechannelid",
    "cubeaccountid",
    "cubelanguagetype",
    "cubemessageid",
}


def _extract_sender(payload: dict[str, Any]) -> dict[str, Any] | None:
    rich_message = payload.get("richnotificationmessage")
    if isinstance(rich_message, dict):
        header = rich_message.get("header")
    else:
        header = payload.get("header")
    sender = header.get("from") if isinstance(header, dict) else None
    return sender if isinstance(sender, dict) else None


def _extract_text_values(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value is None:
        values = []
    else:
        values = [value]
    return [text for item in values if (text := str(item).strip())]


def _extract_callback_message_lines(payload: dict[str, Any]) -> list[str]:
    result = payload.get("result")
    resultdata = result.get("resultdata") if isinstance(result, dict) else None
    if not isinstance(resultdata, list):
        return []

    lines: list[str] = []
    for item in resultdata:
        if not isinstance(item, dict):
            continue

        request_id = str(item.get("requestid") or item.get("processid") or "").strip()
        if request_id.lower() in _SYSTEM_RESULT_REQUEST_IDS:
            continue

        text_value = ", ".join(_extract_text_values(item.get("text")))
        raw_value = ", ".join(_extract_text_values(item.get("value")))
        if text_value and raw_value and text_value != raw_value:
            rendered_value = f"{text_value} ({raw_value})"
        else:
            rendered_value = text_value or raw_value

        if request_id and rendered_value:
            lines.append(f"{request_id}: {rendered_value}")
        elif request_id:
            lines.append(request_id)
        elif rendered_value:
            lines.append(rendered_value)

    return lines


def _extract_callback_message(payload: dict[str, Any]) -> str:
    lines = _extract_callback_message_lines(payload)
    if lines:
        return "\n".join(lines)

    process = payload.get("process")
    processdata = process.get("processdata") if isinstance(process, dict) else None
    if isinstance(processdata, str):
        return processdata.strip()
    return ""


def _build_callback_message_id(payload: dict[str, Any], sender: dict[str, Any]) -> str:
    process = payload.get("process")
    session = process.get("session") if isinstance(process, dict) else None
    signature_payload = {
        "channel_id": str(sender.get("channelid") or ""),
        "original_message_id": str(sender.get("messageid") or ""),
        "sessionid": str(session.get("sessionid") or "") if isinstance(session, dict) else "",
        "sequence": str(session.get("sequence") or "") if isinstance(session, dict) else "",
        "message_lines": _extract_callback_message_lines(payload),
        "processdata": process.get("processdata") if isinstance(process, dict) else "",
    }
    digest = hashlib.sha1(
        json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    prefix = str(sender.get("messageid") or "rich-callback").strip() or "rich-callback"
    return f"{prefix}:callback:{digest}"


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

    sender = _extract_sender(payload)
    if sender is None:
        return None
    nested_user_id = sender.get("uniquename")
    if not nested_user_id:
        return None
    return str(nested_user_id)


def extract_cube_request_fields(payload: dict[str, Any]) -> dict[str, str | None] | None:
    user_id = extract_user_id(payload) or "unknown"

    rich_message = payload.get("richnotificationmessage")
    if isinstance(rich_message, dict):
        process = rich_message.get("process")
        sender = _extract_sender(payload)
        if not isinstance(sender, dict) or not isinstance(process, dict):
            return None
        return {
            "user_id": user_id,
            "message_id": str(sender.get("messageid") or ""),
            "channel_id": str(sender.get("channelid") or ""),
            "user_name": str(sender.get("username") or ""),
            "message": process.get("processdata"),
        }

    sender = _extract_sender(payload)
    process = payload.get("process")
    if isinstance(sender, dict) and isinstance(process, dict):
        return {
            "user_id": user_id,
            "message_id": _build_callback_message_id(payload, sender),
            "channel_id": str(sender.get("channelid") or ""),
            "user_name": str(sender.get("username") or ""),
            "message": _extract_callback_message(payload),
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


def build_multimessage_payload(*, user_id: str, reply_message: str) -> dict[str, Any]:
    return {
        "uniqueName": config.CUBE_API_ID,
        "token": config.CUBE_API_TOKEN,
        "uniqueNameList": [user_id],
        "channelList": [],
        "msg": reply_message,
    }


def build_richnotification_payload(
    *,
    user_id: str,
    channel_id: str,
    reply_message: str | None = None,
    content_items: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if content_items is not None:
        return rich_blocks.build_richnotification(
            from_id=config.CUBE_BOT_ID,
            token=config.CUBE_BOT_TOKEN,
            from_usernames=config.CUBE_BOT_USERNAMES,
            user_id=user_id,
            channel_id=channel_id,
            content_items=content_items,
        )

    message = reply_message or ""
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
            "content": build_richnotification_content(message),
            "result": build_richnotification_result(message),
        }
    }
