"""Raw Cube richnotification JSON 파일을 그대로 Cube에 보내 렌더링을 확인한다.

사용법
------
1. ``config.py``의 자격증명/대상 ID를 본인 값으로 채운다.
2. ``main()`` 안에서 보고 싶은 샘플 함수의 주석만 풀고 실행한다.
3. IDE의 Run 버튼이나 다음 명령으로 바로 실행 (``python -m`` 불필요)::

       python raw_rich_test.py

각 샘플은 같은 디렉터리의 JSON(또는 확장자 없는) 파일을 읽어 ``richnotification``
헤더/콜백 주소만 ``config.py`` 값으로 채운 뒤 그대로 POST한다.
"""

import copy
import json
import logging
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 단독 실행(`python raw_rich_test.py`) 시 프로젝트 루트를 sys.path에 추가해
# `devtools.cube_message...` 절대 임포트가 동작하도록 한다.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# ---------------------------------------------------------------------------

from devtools.cube_message.client import (  # noqa: E402
    CubeMessageConfig,
    CubeMessageError,
    send_raw_richnotification,
)
from devtools.cube_message.raw_richnotification_test import config as raw_config  # noqa: E402

RAW_RICHNOTIFICATION_TEST_DIR = Path(__file__).resolve().parent

FILL_HEADER = True
FILL_CALLBACK = True

USER_ID = raw_config.HEADER_TO_UNIQUENAME
CHANNEL_ID = raw_config.HEADER_TO_CHANNELID


def build_cube_message_config() -> CubeMessageConfig:
    """``config.py``를 우선 사용하고 비어 있는 항목만 ``.env``로 보충한다."""

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
    """절대 경로 또는 ``raw_richnotification_test/`` 하위 이름을 모두 받아 해석."""

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
    """``raw_richnotification_test/`` 하위 raw richnotification 샘플 목록."""

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
    """런타임 보정 없이 raw richnotification JSON을 그대로 로드."""

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
    """raw 페이로드 사본에 ``config.py`` 헤더/콜백 기본값을 채운다."""

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
    """샘플 JSON을 로드해 Cube로 POST."""

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
    result = send_raw_richnotification(
        payload,
        fill_header=False,
        fill_callback=False,
        config=cfg,
    )
    print(json.dumps(result or {"ok": True}, ensure_ascii=False, indent=2))
    return result


def sample_text_summary() -> None:
    """텍스트 요약 카드 샘플."""

    send_raw_file("text_summary.json")


def sample_grid_table() -> None:
    """그리드 테이블 샘플."""

    send_raw_file("grid_table.json")


def sample_select_callback() -> None:
    """select 콜백 샘플 (callbackaddress가 비어 있으면 config 값으로 채운다)."""

    send_raw_file("select_callback.json")


def sample_extensionless() -> None:
    """확장자 없는 raw 페이로드 샘플."""

    send_raw_file("extensionless_sample")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    user_id = raw_config.HEADER_TO_UNIQUENAME
    if FILL_HEADER and (not user_id or user_id.startswith("your.")):
        raise SystemExit("config.py의 HEADER_TO_UNIQUENAME을 본인 Cube ID로 바꿔야 실행할 수 있습니다.")

    # 보내고 싶은 샘플의 주석만 풀어서 실행한다.
    sample_text_summary()
    # sample_grid_table()
    # sample_select_callback()
    # sample_extensionless()


def _configured_usernames(fallback: tuple[str, ...]) -> tuple[str, ...]:
    configured = raw_config.HEADER_FROMUSERNAME
    if isinstance(configured, str):
        return (configured,) if configured else fallback
    values = tuple(name for name in configured if name)
    return values or fallback


def _lang5(values: tuple[str, ...]) -> list[str]:
    padded = list(values) + [""] * 5
    return padded[:5]


if __name__ == "__main__":
    main()
