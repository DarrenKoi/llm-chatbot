"""Standalone Cube richnotification payload builders and senders."""

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from devtools.cube_message.common import (
    CubeMessageConfig,
    CubeMessageError,
    print_json,
    redact_tokens,
    require_config_value,
    send_cube_request,
)
from devtools.cube_message.richnotification import blocks as rich_blocks


def build_richnotification_content(reply_message: str) -> dict[str, str]:
    return {"text": reply_message}


def build_richnotification_result(reply_message: str) -> dict[str, str]:
    return {
        "status": "success",
        "message": reply_message,
    }


def build_richnotification_payload(
    *,
    user_id: str,
    channel_id: str,
    reply_message: str | None = None,
    content_items: Iterable[dict[str, Any]] | None = None,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or CubeMessageConfig.from_env()
    if content_items is not None:
        return rich_blocks.build_richnotification(
            from_id=resolved_config.bot_id,
            token=resolved_config.bot_token,
            from_usernames=resolved_config.bot_usernames,
            user_id=user_id,
            channel_id=channel_id,
            content_items=content_items,
        )

    message = reply_message or ""
    return {
        "richnotification": {
            "header": {
                "from": resolved_config.bot_id,
                "token": resolved_config.bot_token,
                "fromusername": list(resolved_config.bot_usernames),
                "to": {
                    "uniquename": [user_id],
                    "channelid": [channel_id],
                },
            },
            "content": build_richnotification_content(message),
            "result": build_richnotification_result(message),
        }
    }


def send_richnotification(
    *,
    user_id: str,
    channel_id: str,
    reply_message: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    resolved_config = config or CubeMessageConfig.from_env()
    _validate_richnotification_config(resolved_config)

    payload = build_richnotification_payload(
        user_id=user_id,
        channel_id=channel_id,
        reply_message=reply_message,
        config=resolved_config,
    )
    return _send_richnotification_payload(payload=payload, config=resolved_config)


def send_richnotification_blocks(
    *message_blocks: rich_blocks.Block,
    user_id: str,
    channel_id: str,
    callback_address: str | None = None,
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    resolved_config = config or CubeMessageConfig.from_env()
    _validate_richnotification_config(resolved_config)

    resolved_callback_address = callback_address
    if resolved_callback_address is None:
        resolved_callback_address = (
            resolved_config.richnotification_callback_url if any(block.requestid for block in message_blocks) else ""
        )

    content_item = rich_blocks.add_container(
        *message_blocks,
        callback_address=resolved_callback_address,
        session_id=session_id,
        sequence=sequence,
        summary=summary,
    )
    payload = build_richnotification_payload(
        user_id=user_id,
        channel_id=channel_id,
        content_items=[content_item],
        config=resolved_config,
    )
    return _send_richnotification_payload(payload=payload, config=resolved_config)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a standalone Cube richnotification from devtools.")
    parser.add_argument("--user-id", required=True, help="Cube target user uniqueName.")
    parser.add_argument("--channel-id", required=True, help="Cube target channel ID.")
    parser.add_argument("--message", required=True, help="Message text to send.")
    parser.add_argument("--env-file", type=Path, default=None, help="Optional env file path. Defaults to .env.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request payload without sending it.")
    args = parser.parse_args(argv)

    config = CubeMessageConfig.from_env(args.env_file)
    try:
        if args.dry_run:
            payload = build_richnotification_payload(
                user_id=args.user_id,
                channel_id=args.channel_id,
                reply_message=args.message,
                config=config,
            )
            print_json(redact_tokens(payload))
            return 0

        result = send_richnotification(
            user_id=args.user_id,
            channel_id=args.channel_id,
            reply_message=args.message,
            config=config,
        )
        print_json(result)
    except CubeMessageError as exc:
        parser.exit(1, f"{exc}\n")
    return 0


def _validate_richnotification_config(config: CubeMessageConfig) -> None:
    require_config_value(config.richnotification_url, "CUBE_RICHNOTIFICATION_URL")
    require_config_value(config.bot_id, "CUBE_BOT_ID")
    require_config_value(config.bot_token, "CUBE_BOT_TOKEN")


def _send_richnotification_payload(
    *,
    payload: dict[str, Any],
    config: CubeMessageConfig,
) -> dict[str, Any] | None:
    return send_cube_request(
        url=config.richnotification_url,
        payload=payload,
        label="richnotification",
        timeout_seconds=config.timeout_seconds,
    )
