"""Shared standalone Cube message utilities.

This module intentionally does not import ``api.config`` so the devtools
message senders can run outside the Flask application context.
"""

import copy
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_CUBE_API_URL = "http://cube.skhynix.com:8888"
DEFAULT_WEB_APP_URL = "http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com"


class CubeMessageError(RuntimeError):
    """Raised when standalone Cube message delivery fails."""


@dataclass(frozen=True)
class CubeMessageConfig:
    """Environment-backed Cube settings for standalone devtools senders."""

    api_id: str
    api_token: str
    api_url: str
    multimessage_url: str
    richnotification_url: str
    bot_id: str
    bot_token: str
    bot_usernames: tuple[str, ...]
    richnotification_callback_url: str
    timeout_seconds: float

    @classmethod
    def from_env(cls, env_file: Path | None = None, *, load_env: bool = True) -> "CubeMessageConfig":
        if load_env:
            load_standalone_env(env_file)

        api_id = os.environ.get("CUBE_API_ID", "")
        api_token = os.environ.get("CUBE_API_TOKEN", "")
        api_url = os.environ.get("CUBE_API_URL", DEFAULT_CUBE_API_URL).rstrip("/")
        bot_name = os.environ.get("CUBE_BOT_NAME", "ITC OSS")
        bot_usernames = _split_names(os.environ.get("CUBE_BOT_USERNAMES", bot_name))
        web_app_url = os.environ.get("WEB_APP_URL", DEFAULT_WEB_APP_URL).rstrip("/")
        return cls(
            api_id=api_id,
            api_token=api_token,
            api_url=api_url,
            multimessage_url=os.environ.get("CUBE_MULTIMESSAGE_URL", f"{api_url}/api/multiMessage"),
            richnotification_url=os.environ.get(
                "CUBE_RICHNOTIFICATION_URL",
                f"{api_url}/legacy/richnotification",
            ),
            bot_id=os.environ.get("CUBE_BOT_ID", api_id),
            bot_token=os.environ.get("CUBE_BOT_TOKEN", api_token),
            bot_usernames=bot_usernames,
            richnotification_callback_url=os.environ.get(
                "CUBE_RICHNOTIFICATION_CALLBACK_URL",
                f"{web_app_url}/api/v1/cube/richnotification/callback",
            ).rstrip("/"),
            timeout_seconds=float(os.environ.get("CUBE_TIMEOUT_SECONDS", "10")),
        )


def load_standalone_env(env_file: Path | None = None) -> Path | None:
    """Load a project env file without importing the application config."""

    selected_env_file = env_file or _default_env_file()
    if selected_env_file is None or not selected_env_file.exists():
        return None

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_dotenv_fallback(selected_env_file)
    else:
        load_dotenv(selected_env_file, override=False)
    return selected_env_file


def send_cube_request(
    *,
    url: str,
    payload: dict[str, Any],
    label: str,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    """Send one Cube HTTP request and normalize the response body."""

    logger.info("Cube %s request started", label)
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = f"Cube {label} failed with HTTP {exc.response.status_code}: {exc.response.text}"
        raise CubeMessageError(message) from exc
    except httpx.RequestError as exc:
        raise CubeMessageError(f"Cube {label} failed: {exc}") from exc

    if not response.content:
        logger.info("Cube %s request completed: empty_response=True", label)
        return None

    try:
        data = response.json()
    except json.JSONDecodeError:
        logger.info("Cube %s request completed: raw_text=True", label)
        return {"raw": response.text}

    if not isinstance(data, dict):
        logger.info("Cube %s request completed: wrapped=True", label)
        return {"payload": data}

    logger.info("Cube %s request completed", label)
    return data


def require_config_value(value: str, name: str) -> None:
    if not value:
        raise CubeMessageError(f"{name} is not configured.")


def redact_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with token fields hidden for CLI dry-runs."""

    redacted = copy.deepcopy(payload)
    _redact_value(redacted)
    return redacted


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _default_env_file() -> Path | None:
    project_root = Path(__file__).resolve().parents[2]
    env_file = project_root / ".env"
    if env_file.exists():
        return env_file

    example_env_file = project_root / ".env.example"
    if example_env_file.exists():
        return example_env_file
    return None


def _split_names(value: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in value.split(",") if name.strip())


def _load_dotenv_fallback(env_file: Path) -> None:
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _redact_value(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() == "token" and item:
                value[key] = "<redacted>"
            else:
                _redact_value(item)
    elif isinstance(value, list):
        for item in value:
            _redact_value(item)
