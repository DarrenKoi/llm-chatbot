"""사용자 프로필 조회 서비스를 제공한다."""

import importlib
import logging
from collections.abc import Callable
from typing import Any

import httpx
import redis

from api import config
from api.profile.models import UserProfile

log = logging.getLogger(__name__)


def load_user_profile(user_id: str) -> UserProfile | None:
    """사용자 프로필을 조회한다."""

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        return None

    for loader in (_load_from_custom_provider, _load_from_profile_api, _load_from_redis):
        profile = loader(normalized_user_id)
        if profile is not None:
            return profile

    return None


def _load_from_custom_provider(user_id: str) -> UserProfile | None:
    provider_path = config.USER_PROFILE_PROVIDER_CALLABLE.strip()
    if not provider_path:
        return None

    try:
        provider = _resolve_provider(provider_path)
        payload = provider(user_id)
    except Exception as exc:
        log.warning("custom_profile_provider_failed user_id=%s error=%s", user_id, exc)
        return None

    return _coerce_profile(payload, user_id=user_id, default_source="custom_provider")


def _resolve_provider(provider_path: str) -> Callable[[str], object]:
    module_name, separator, attr_name = provider_path.partition(":")
    if not separator or not module_name or not attr_name:
        raise ValueError("USER_PROFILE_PROVIDER_CALLABLE must look like 'module.path:function_name'.")

    module = importlib.import_module(module_name)
    provider = getattr(module, attr_name)
    if not callable(provider):
        raise TypeError(f"{provider_path} is not callable.")
    return provider


def _load_from_profile_api(user_id: str) -> UserProfile | None:
    template = config.USER_PROFILE_API_URL.strip()
    if not template:
        return None

    url = template.format(user_id=user_id)

    try:
        response = httpx.get(url, timeout=config.USER_PROFILE_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        log.warning("profile_api_lookup_failed user_id=%s error=%s", user_id, exc)
        return None

    return _coerce_profile(payload, user_id=user_id, default_source="profile_api")


def _load_from_redis(user_id: str) -> UserProfile | None:
    redis_url = config.USER_PROFILE_REDIS_URL.strip()
    if not redis_url:
        return None

    key = f"{config.USER_PROFILE_REDIS_KEY_PREFIX}:{user_id}"
    client = None

    try:
        client = redis.from_url(
            redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=False,
        )
        raw = client.hgetall(key)
    except Exception as exc:
        log.warning("profile_redis_lookup_failed user_id=%s error=%s", user_id, exc)
        return None
    finally:
        if client is not None:
            _close_redis_client(client)

    if not raw:
        return None

    payload = {
        _decode_redis_value(field): _decode_redis_value(value)
        for field, value in raw.items()
    }
    return _coerce_profile(payload, user_id=user_id, default_source="redis")


def _coerce_profile(payload: object, *, user_id: str, default_source: str) -> UserProfile | None:
    if payload is None:
        return None
    if isinstance(payload, UserProfile):
        return payload if payload.to_prompt_text().strip() else None
    if not isinstance(payload, dict):
        log.warning("user_profile_payload_invalid user_id=%s payload_type=%s", user_id, type(payload).__name__)
        return None

    return _normalize_profile(payload, user_id=user_id, default_source=default_source)


def _normalize_profile(payload: dict[str, Any], *, user_id: str, default_source: str) -> UserProfile | None:
    name = _clean_text(payload.get("name") or payload.get("user_name"))
    team = _clean_text(payload.get("team") or payload.get("team_name"))
    organization = _clean_text(payload.get("organization") or payload.get("org_name"))
    work_location = _clean_text(
        payload.get("work_location") or payload.get("site") or payload.get("location")
    )
    role = _clean_text(payload.get("role") or payload.get("job_title") or payload.get("position"))
    email = _clean_text(payload.get("email"))
    source = _clean_text(payload.get("source")) or default_source

    if not any([name, team, organization, work_location, role, email]):
        return None

    return UserProfile(
        user_id=user_id,
        name=name,
        team=team,
        organization=organization,
        work_location=work_location,
        role=role,
        email=email,
        source=source,
    )


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _decode_redis_value(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _close_redis_client(client: object) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()
