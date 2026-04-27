"""Post raw Cube richnotification JSON files for rendering checks.

Edit the constants below or pass CLI arguments when running:

    python -m devtools.cube_message.raw_rich_test --file text_summary.json --user-id my.cube.id

The JSON file should contain the complete ``{"richnotification": ...}``
payload. By default this script replaces only the top-level auth/target header
with local config values before posting.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from devtools.cube_message.client import (
    CubeMessageConfig,
    CubeMessageError,
    send_raw_richnotification,
)

RICHNOTIFICATIONS_DIR = Path(__file__).resolve().parent / "richnotifications"

# Edit these for quick IDE runs. Keep CHANNEL_ID as an empty string for direct
# user delivery unless a Cube test case specifically needs a channel id.
CONFIG = CubeMessageConfig.from_env()
RICHNOTIFICATION_FILE = RICHNOTIFICATIONS_DIR / "text_summary.json"
USER_ID = "your.cube.id"
CHANNEL_ID = ""
FILL_HEADER = True
FILL_CALLBACK = True


def resolve_richnotification_file(path_or_name: str | Path) -> Path:
    """Resolve either an absolute path or a name under richnotifications/."""

    path = Path(path_or_name)
    if not path.suffix:
        path = path.with_suffix(".json")
    if path.is_absolute() or path.exists():
        return path
    return RICHNOTIFICATIONS_DIR / path


def list_richnotification_files() -> list[Path]:
    """Return available raw richnotification JSON files."""

    return sorted(RICHNOTIFICATIONS_DIR.glob("*.json"))


def load_raw_richnotification(path_or_name: str | Path) -> dict[str, Any]:
    """Load and validate a complete raw richnotification JSON file."""

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


def send_raw_file(
    path_or_name: str | Path,
    *,
    user_id: str | None = None,
    channel_id: str = CHANNEL_ID,
    fill_header: bool = FILL_HEADER,
    fill_callback: bool = FILL_CALLBACK,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """Load a raw JSON file and POST it to Cube."""

    payload = load_raw_richnotification(path_or_name)
    return send_raw_richnotification(
        payload,
        user_id=user_id,
        channel_id=channel_id,
        fill_header=fill_header,
        fill_callback=fill_callback,
        config=config or CONFIG,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()

    if args.list:
        for path in list_richnotification_files():
            print(path.name)
        return

    selected_file = args.file or RICHNOTIFICATION_FILE
    user_id = args.user_id if args.user_id is not None else USER_ID
    channel_id = args.channel_id if args.channel_id is not None else CHANNEL_ID
    fill_header = not args.keep_header

    if fill_header and (not user_id or user_id.startswith("your.")):
        raise SystemExit("USER_ID를 본인 Cube ID로 바꾸거나 --user-id를 지정해야 합니다.")

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
    parser.add_argument("--file", help="JSON file name under richnotifications/ or an explicit path.")
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
    parser.add_argument("--list", action="store_true", help="List available richnotifications/*.json files.")
    return parser.parse_args()


if __name__ == "__main__":
    main()
