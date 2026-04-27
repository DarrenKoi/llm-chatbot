"""Post raw Cube richnotification JSON files for rendering checks.

Edit the constants below or pass CLI arguments when running:

    python -m devtools.cube_message.raw_richnotification_test --file text_summary.json --user-id my.cube.id

The JSON file should contain the complete ``{"richnotification": ...}``
payload. By default this script replaces only the top-level auth/target header
with local config values before posting.
"""

import argparse
import copy
import json
import logging
from pathlib import Path
from typing import Any

from devtools.cube_message.client import (
    CubeMessageConfig,
    CubeMessageError,
    send_raw_richnotification,
)
from devtools.cube_message.raw_richnotification_test import config as raw_config

RAW_RICHNOTIFICATION_TEST_DIR = Path(__file__).resolve().parent

# Edit config.py for quick IDE runs. Keep CHANNEL_ID as an empty string for
# direct user delivery unless a Cube test case specifically needs a channel id.
RICHNOTIFICATION_FILE = RAW_RICHNOTIFICATION_TEST_DIR / "text_summary.json"
FILL_HEADER = True
FILL_CALLBACK = True


def build_cube_message_config() -> CubeMessageConfig:
    """Build send config from raw-test config.py, falling back to .env."""

    base = CubeMessageConfig.from_env()
    return CubeMessageConfig(
        richnotification_url=raw_config.RICHNOTIFICATION_URL or base.richnotification_url,
        bot_id=raw_config.HEADER_FROM or base.bot_id,
        bot_token=raw_config.HEADER_TOKEN or base.bot_token,
        bot_usernames=_configured_usernames(base.bot_usernames),
        callback_url=raw_config.PROCESS_CALLBACKADDRESS or base.callback_url,
        timeout_seconds=raw_config.TIMEOUT_SECONDS or base.timeout_seconds,
    )


def resolve_richnotification_file(path_or_name: str | Path) -> Path:
    """Resolve either an absolute path or a name under raw_richnotification_test/."""

    path = Path(path_or_name)
    candidates = [path]
    if not path.suffix:
        candidates.append(path.with_suffix(".json"))
    if not path.is_absolute():
        candidates.append(RAW_RICHNOTIFICATION_TEST_DIR / path)
        if not path.suffix:
            candidates.append(RAW_RICHNOTIFICATION_TEST_DIR / path.with_suffix(".json"))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path if path.is_absolute() else RAW_RICHNOTIFICATION_TEST_DIR / path


def list_richnotification_files() -> list[Path]:
    """Return available raw richnotification JSON files."""

    return sorted(
        path
        for path in RAW_RICHNOTIFICATION_TEST_DIR.iterdir()
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.name != "__init__.py"
            and path.suffix in ("", ".json")
        )
    )


def load_raw_richnotification(path_or_name: str | Path) -> dict[str, Any]:
    """Load a raw richnotification JSON file without applying runtime defaults."""

    path = resolve_richnotification_file(path_or_name)
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except OSError as exc:
        raise CubeMessageError(f"raw richnotification 파일을 읽을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CubeMessageError(f"raw richnotification JSON 형식이 올바르지 않습니다: {path}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("richnotification"), dict):
        raise CubeMessageError("raw richnotification 파일은 'richnotification' 객체를 포함해야 합니다.")
    return payload


def apply_raw_test_config(
    payload: dict[str, Any],
    *,
    user_id: str | None = None,
    channel_id: str | None = None,
    fill_header: bool = FILL_HEADER,
    fill_callback: bool = FILL_CALLBACK,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any]:
    """Apply config.py header and process defaults to a raw payload copy."""

    prepared = copy.deepcopy(payload)
    rich = prepared["richnotification"]
    cfg = config or build_cube_message_config()

    if fill_header:
        header = rich.setdefault("header", {})
        if not isinstance(header, dict):
            header = {}
            rich["header"] = header
        to_header = header.setdefault("to", {})
        if not isinstance(to_header, dict):
            to_header = {}
            header["to"] = to_header

        header["from"] = cfg.bot_id
        header["token"] = cfg.bot_token
        header["fromusername"] = _lang5(cfg.bot_usernames)
        to_header["uniquename"] = [user_id if user_id is not None else raw_config.HEADER_TO_UNIQUENAME]
        to_header["channelid"] = [channel_id if channel_id is not None else raw_config.HEADER_TO_CHANNELID]

    content = rich.get("content")
    if fill_callback and isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            process = item.setdefault("process", {})
            if not isinstance(process, dict):
                continue
            if not process.get("callbacktype"):
                process["callbacktype"] = raw_config.PROCESS_CALLBACKTYPE
            if process.get("callbacktype") == "url":
                process["callbackaddress"] = cfg.callback_url

    return prepared


def send_raw_file(
    path_or_name: str | Path,
    *,
    user_id: str | None = None,
    channel_id: str | None = None,
    fill_header: bool = FILL_HEADER,
    fill_callback: bool = FILL_CALLBACK,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """Load a raw JSON file and POST it to Cube."""

    cfg = config or build_cube_message_config()
    raw_payload = load_raw_richnotification(path_or_name)
    payload = apply_raw_test_config(
        raw_payload,
        user_id=user_id,
        channel_id=channel_id,
        fill_header=fill_header,
        fill_callback=fill_callback,
        config=cfg,
    )
    return send_raw_richnotification(
        payload,
        fill_header=False,
        fill_callback=False,
        config=cfg,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()

    if args.list:
        for path in list_richnotification_files():
            print(path.name)
        return

    selected_file = args.file or RICHNOTIFICATION_FILE
    user_id = args.user_id if args.user_id is not None else raw_config.HEADER_TO_UNIQUENAME
    channel_id = args.channel_id if args.channel_id is not None else raw_config.HEADER_TO_CHANNELID
    fill_header = not args.keep_header

    if fill_header and (not user_id or user_id.startswith("your.")):
        raise SystemExit("config.py의 HEADER_TO_UNIQUENAME을 바꾸거나 --user-id를 지정해야 합니다.")

    result = send_raw_file(
        selected_file,
        user_id=user_id,
        channel_id=channel_id,
        fill_header=fill_header,
        fill_callback=not args.keep_callback,
    )
    print(json.dumps(result or {"ok": True}, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post a raw Cube richnotification JSON file.")
    parser.add_argument(
        "--file",
        help="JSON file name under raw_richnotification_test/ or an explicit path. .json is optional.",
    )
    parser.add_argument("--user-id", help="Cube uniquename to replace in the header.")
    parser.add_argument("--channel-id", help="Cube channel id to replace in the header. Default is empty.")
    parser.add_argument(
        "--keep-header",
        action="store_true",
        help="Post the JSON header exactly as the file contains it.",
    )
    parser.add_argument(
        "--keep-callback",
        action="store_true",
        help="Do not fill empty URL callback addresses from config.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available raw richnotification sample files.",
    )
    return parser.parse_args()


def _configured_usernames(fallback: tuple[str, ...]) -> tuple[str, ...]:
    configured = raw_config.HEADER_FROMUSERNAME
    if isinstance(configured, str):
        return (configured,) if configured else fallback
    values = tuple(name for name in configured if name)
    return values or fallback


def _lang5(values: tuple[str, ...]) -> list[str]:
    padded = list(values) + [""] * 5
    return padded[:5]


USER_ID = raw_config.HEADER_TO_UNIQUENAME
CHANNEL_ID = raw_config.HEADER_TO_CHANNELID


if __name__ == "__main__":
    main()
