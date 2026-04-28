"""Raw Cube richnotification JSON 파일을 그대로 Cube에 보내 렌더링을 확인한다.

사용법
------
1. ``config.py``의 자격증명/대상 ID를 본인 값으로 채운다.
2. ``main()`` 안에서 보고 싶은 샘플 함수의 주석만 풀고 실행한다.
3. IDE의 Run 버튼이나 다음 명령으로 바로 실행 (``python -m`` 불필요)::

       python raw_rich_test.py

각 샘플은 ``samples/`` 디렉터리의 JSON(또는 확장자 없는) 파일을 읽어
``richnotification`` 헤더/콜백 주소만 ``config.py`` 값으로 채운 뒤 그대로 POST한다.

여러 샘플을 한 번에 검증하고 싶으면 ``sample_all()``을 호출한다. Cube 대역폭
보호를 위해 각 전송 사이에 ``ITERATION_DELAY_SECONDS``(기본 2초)만큼 대기한다.
"""

import copy
import json
import logging
import sys
import time
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
SAMPLES_DIR = RAW_RICHNOTIFICATION_TEST_DIR / "samples"

FILL_HEADER = True
FILL_CALLBACK = True

# Cube 대역폭/연속 전송 보호용 기본 간격 (초).
ITERATION_DELAY_SECONDS = 2.0

USER_ID = raw_config.HEADER_TO_UNIQUENAME
CHANNEL_ID = raw_config.HEADER_TO_CHANNELID


def _configured_usernames(fallback: tuple[str, ...]) -> tuple[str, ...]:
    configured = raw_config.HEADER_FROMUSERNAME
    if isinstance(configured, str):
        return (configured,) if configured else fallback
    values = tuple(name for name in configured if name)
    return values or fallback


def _lang5(values: tuple[str, ...]) -> list[str]:
    """fromusername: 단일 값이면 5개 슬롯 모두에 동일하게 채운다."""

    if len(values) == 1:
        return [values[0]] * 5
    padded = list(values) + [""] * 5
    return padded[:5]


def _resolve_samples_folder(folder: str | Path | None) -> Path:
    """폴더 인자를 절대 경로로 해석. 상대 경로는 패키지 디렉터리 기준을 우선한다."""

    if folder is None:
        return SAMPLES_DIR
    path = Path(folder)
    if path.is_absolute():
        return path
    package_relative = RAW_RICHNOTIFICATION_TEST_DIR / path
    if package_relative.exists():
        return package_relative
    return path


def build_cube_message_config() -> CubeMessageConfig:
    """``config.py``를 우선 사용하고 비어 있는 항목만 ``.env``로 보충한다."""

    base = CubeMessageConfig.from_env()
    return CubeMessageConfig(
        richnotification_url=base.richnotification_url,
        bot_id=raw_config.HEADER_FROM or base.bot_id,
        bot_token=raw_config.HEADER_TOKEN or base.bot_token,
        bot_usernames=_configured_usernames(base.bot_usernames),
        callback_url=raw_config.PROCESS_CALLBACKADDRESS or base.callback_url,
        timeout_seconds=raw_config.TIMEOUT_SECONDS or base.timeout_seconds,
    )


def resolve_richnotification_file(path_or_name: str | Path) -> Path:
    """절대 경로 또는 ``samples/`` 하위 이름을 모두 받아 해석."""

    path = Path(path_or_name)
    candidates = [path]
    if not path.suffix:
        candidates.append(path.with_suffix(".json"))
    if not path.is_absolute():
        candidates.append(SAMPLES_DIR / path)
        if not path.suffix:
            candidates.append(SAMPLES_DIR / path.with_suffix(".json"))
        # 이전 위치(테스트 디렉터리 직접 하위)에 둔 샘플도 호환을 위해 검사.
        candidates.append(RAW_RICHNOTIFICATION_TEST_DIR / path)
        if not path.suffix:
            candidates.append(RAW_RICHNOTIFICATION_TEST_DIR / path.with_suffix(".json"))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path if path.is_absolute() else SAMPLES_DIR / path


def list_richnotification_files(folder: str | Path | None = None) -> list[Path]:
    """``samples/``(기본) 또는 지정한 폴더 안의 raw richnotification 샘플 목록."""

    target = _resolve_samples_folder(folder)
    if not target.exists():
        return []
    return sorted(
        path
        for path in target.iterdir()
        if (path.is_file() and not path.name.startswith(".") and path.suffix in ("", ".json"))
    )


def load_raw_richnotification(path_or_name: str | Path) -> dict[str, Any]:
    """런타임 보정 없이 raw richnotification JSON을 그대로 로드."""

    path = resolve_richnotification_file(path_or_name)
    try:
        # utf-8-sig: BOM이 붙은 Windows 저장 JSON도 그대로 읽을 수 있게 한다.
        with path.open(encoding="utf-8-sig") as file:
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


def send_all_samples(
    folder: str | Path | None = None,
    *,
    delay_seconds: float = ITERATION_DELAY_SECONDS,
    user_id: str | None = None,
    channel_id: str | None = None,
) -> list[dict[str, Any] | None]:
    """지정한 폴더(기본 ``samples/``)의 모든 샘플을 ``delay_seconds`` 간격으로 순차 전송."""

    cfg = build_cube_message_config()
    target = _resolve_samples_folder(folder)
    files = list_richnotification_files(target)
    if not files:
        raise CubeMessageError(f"샘플 디렉터리에서 보낼 파일을 찾지 못했습니다: {target}")

    results: list[dict[str, Any] | None] = []
    total = len(files)
    print(f"📂 {target} (총 {total}개)")
    for index, path in enumerate(files):
        if index > 0 and delay_seconds > 0:
            print(f"  ⏳ {delay_seconds}s 대기 후 다음 샘플 전송")
            time.sleep(delay_seconds)
        print(f"[{index + 1}/{total}] {path.name}")
        results.append(
            send_raw_file(
                path,
                user_id=user_id,
                channel_id=channel_id,
                config=cfg,
            )
        )
    return results


def sample_all(folder: str | Path | None = None) -> None:
    """지정한 폴더(기본 ``samples/``)의 모든 샘플을 ``ITERATION_DELAY_SECONDS`` 간격으로 전송."""

    send_all_samples(folder)


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

    # --- 단일 파일 직접 지정 (확장자 생략 가능, 절대 경로도 OK) ---
    # send_raw_file("samples/Sample20.json")
    # send_raw_file("samples/test1")
    # send_raw_file("Sample20")              # samples/ 하위 이름만 적어도 자동 탐색
    # send_raw_file("/abs/path/to/payload.json")

    # --- 폴더 단위 일괄 전송 (요청 사이 2초 대기) ---
    # sample_all()                     # samples/ 안의 모든 파일을 순회 전송
    # sample_all("experimental")       # raw_richnotification_test/experimental/ 폴더 사용
    # sample_all("/abs/path/to/dir")   # 절대 경로도 지원


if __name__ == "__main__":
    main()
