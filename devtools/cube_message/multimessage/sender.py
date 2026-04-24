"""Standalone Cube multiMessage payload builder and sender."""

import argparse
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


def build_multimessage_payload(
    *,
    user_id: str,
    reply_message: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any]:
    resolved_config = config or CubeMessageConfig.from_env()
    return {
        "uniqueName": resolved_config.api_id,
        "token": resolved_config.api_token,
        "uniqueNameList": [user_id],
        "channelList": [],
        "msg": reply_message,
    }


def send_multimessage(
    *,
    user_id: str,
    reply_message: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    resolved_config = config or CubeMessageConfig.from_env()
    require_config_value(resolved_config.multimessage_url, "CUBE_MULTIMESSAGE_URL")
    require_config_value(resolved_config.api_id, "CUBE_API_ID")
    require_config_value(resolved_config.api_token, "CUBE_API_TOKEN")

    payload = build_multimessage_payload(
        user_id=user_id,
        reply_message=reply_message,
        config=resolved_config,
    )
    return send_cube_request(
        url=resolved_config.multimessage_url,
        payload=payload,
        label="multiMessage",
        timeout_seconds=resolved_config.timeout_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a standalone Cube multiMessage from devtools.")
    parser.add_argument("--user-id", required=True, help="Cube target user uniqueName.")
    parser.add_argument("--message", required=True, help="Message text to send.")
    parser.add_argument("--env-file", type=Path, default=None, help="Optional env file path. Defaults to .env.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request payload without sending it.")
    args = parser.parse_args(argv)

    config = CubeMessageConfig.from_env(args.env_file)
    try:
        if args.dry_run:
            payload = build_multimessage_payload(
                user_id=args.user_id,
                reply_message=args.message,
                config=config,
            )
            print_json(redact_tokens(payload))
            return 0

        result = send_multimessage(
            user_id=args.user_id,
            reply_message=args.message,
            config=config,
        )
        print_json(result)
    except CubeMessageError as exc:
        parser.exit(1, f"{exc}\n")
    return 0
