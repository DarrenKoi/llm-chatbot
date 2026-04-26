"""Cube richnotification 메시지 전송 클라이언트 (devtools 전용).

api.config는 임포트하지 않으며, 프로젝트 루트의 ``.env``에서 직접 설정을 읽는다.
팀원들이 Flask 앱을 띄우지 않고도 Cube에서 메시지가 어떻게 보이는지 확인할 수 있다.
"""

import copy
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from devtools.cube_message import blocks as rich_blocks

logger = logging.getLogger(__name__)

DEFAULT_CUBE_API_URL = "http://cube.skhynix.com:8888"


class CubeMessageError(RuntimeError):
    """Cube 메시지 전송 실패 시 발생."""


@dataclass(frozen=True)
class CubeMessageConfig:
    """devtools 전용 Cube 설정. ``inline()`` 또는 ``from_env()``로 생성."""

    richnotification_url: str
    bot_id: str
    bot_token: str
    bot_usernames: tuple[str, ...]
    callback_url: str
    timeout_seconds: float

    @classmethod
    def inline(
        cls,
        *,
        api_id: str,
        api_token: str,
        bot_username: str = "ITC OSS",
        api_url: str = DEFAULT_CUBE_API_URL,
        callback_url: str = "",
        timeout_seconds: float = 10.0,
    ) -> "CubeMessageConfig":
        """파이썬 코드 안에서 자격증명을 직접 적어 쓰는 단축 생성자.

        ``callback_url``은 봇 서비스마다 다르므로 사용자가 전체 주소를 그대로 넣는다.
        select 등 콜백이 필요한 블록을 쓰지 않으면 빈 문자열로 둔다.
        """

        return cls(
            richnotification_url=f"{api_url.rstrip('/')}/legacy/richnotification",
            bot_id=api_id,
            bot_token=api_token,
            bot_usernames=(bot_username,),
            callback_url=callback_url,
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "CubeMessageConfig":
        _load_env(env_file)

        api_id = os.environ.get("CUBE_API_ID", "")
        api_token = os.environ.get("CUBE_API_TOKEN", "")
        api_url = os.environ.get("CUBE_API_URL", DEFAULT_CUBE_API_URL).rstrip("/")
        bot_name = os.environ.get("CUBE_BOT_NAME", "ITC OSS")
        bot_usernames = tuple(
            name.strip() for name in os.environ.get("CUBE_BOT_USERNAMES", bot_name).split(",") if name.strip()
        )

        return cls(
            richnotification_url=os.environ.get("CUBE_RICHNOTIFICATION_URL", f"{api_url}/legacy/richnotification"),
            bot_id=os.environ.get("CUBE_BOT_ID", api_id),
            bot_token=os.environ.get("CUBE_BOT_TOKEN", api_token),
            bot_usernames=bot_usernames,
            callback_url=os.environ.get("CUBE_RICHNOTIFICATION_CALLBACK_URL", ""),
            timeout_seconds=float(os.environ.get("CUBE_TIMEOUT_SECONDS", "10")),
        )


def send_text(
    text: str,
    *,
    user_id: str,
    channel_id: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """가장 단순한 한 줄 텍스트 전송."""

    return send_blocks(
        rich_blocks.add_text(text),
        user_id=user_id,
        channel_id=channel_id,
        config=config,
    )


def send_blocks(
    *message_blocks: rich_blocks.Block,
    user_id: str,
    channel_id: str,
    callback_address: str | None = None,
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """블록을 모아 richnotification으로 전송."""

    cfg = config or CubeMessageConfig.from_env()
    _require(cfg.richnotification_url, "CUBE_RICHNOTIFICATION_URL")
    _require(cfg.bot_id, "CUBE_BOT_ID")
    _require(cfg.bot_token, "CUBE_BOT_TOKEN")

    resolved_callback = callback_address
    if resolved_callback is None:
        has_request_block = any(block.requestid for block in message_blocks)
        resolved_callback = cfg.callback_url if has_request_block else ""

    container = rich_blocks.add_container(
        *message_blocks,
        callback_address=resolved_callback,
        session_id=session_id,
        sequence=sequence,
        summary=summary,
    )
    payload = rich_blocks.build_richnotification(
        from_id=cfg.bot_id,
        token=cfg.bot_token,
        from_usernames=cfg.bot_usernames,
        user_id=user_id,
        channel_id=channel_id,
        content_items=[container],
    )
    return _post(cfg.richnotification_url, payload, cfg.timeout_seconds)


def send_raw_content(
    content_items: list[dict[str, Any]],
    *,
    user_id: str,
    channel_id: str,
    fill_callback: bool = True,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """검증된 ``content`` 배열을 손대지 않고 그대로 전송.

    헤더(``from`` / ``token`` / ``to``)만 ``config`` 값으로 채우고 본문 구조는
    바꾸지 않는다. ``fill_callback=True``이면 ``callbacktype == "url"``인데
    ``callbackaddress``가 비어 있는 항목에 ``config.callback_url``을 채워 넣는다.
    """

    cfg = config or CubeMessageConfig.from_env()
    _require(cfg.richnotification_url, "CUBE_RICHNOTIFICATION_URL")
    _require(cfg.bot_id, "CUBE_BOT_ID")
    _require(cfg.bot_token, "CUBE_BOT_TOKEN")

    items: list[dict[str, Any]] = list(content_items)
    if fill_callback:
        items = [copy.deepcopy(item) for item in items]
        for item in items:
            process = item.get("process")
            if not isinstance(process, dict):
                continue
            if process.get("callbacktype") == "url" and not process.get("callbackaddress"):
                process["callbackaddress"] = cfg.callback_url

    payload = rich_blocks.build_richnotification(
        from_id=cfg.bot_id,
        token=cfg.bot_token,
        from_usernames=cfg.bot_usernames,
        user_id=user_id,
        channel_id=channel_id,
        content_items=items,
    )
    return _post(cfg.richnotification_url, payload, cfg.timeout_seconds)


def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any] | None:
    logger.info("Cube richnotification 요청 시작")
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CubeMessageError(f"Cube richnotification HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise CubeMessageError(f"Cube richnotification 실패: {exc}") from exc

    if not response.content:
        return None
    try:
        data = response.json()
    except json.JSONDecodeError:
        return {"raw": response.text}
    return data if isinstance(data, dict) else {"payload": data}


def _require(value: str, name: str) -> None:
    if not value:
        raise CubeMessageError(f"{name}이(가) 설정되지 않았습니다.")


def _load_env(env_file: Path | None) -> None:
    selected = env_file
    if selected is None:
        project_root = Path(__file__).resolve().parents[2]
        for candidate in (project_root / ".env", project_root / ".env.example"):
            if candidate.exists():
                selected = candidate
                break
    if selected is not None and selected.exists():
        load_dotenv(selected, override=False)
