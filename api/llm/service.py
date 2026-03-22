import json
from typing import Any

import httpx

from api import config
from api.llm.prompt import get_system_prompt


class LLMServiceError(RuntimeError):
    """Raised when the OpenAI-compatible LLM endpoint cannot provide a reply."""


def generate_reply(*, history: list[dict[str, Any]], user_message: str) -> str:
    base_url = config.LLM_BASE_URL.rstrip("/")
    if not base_url:
        raise LLMServiceError("LLM_BASE_URL is not configured.")
    if not config.LLM_MODEL:
        raise LLMServiceError("LLM_MODEL is not configured.")

    payload = {
        "model": config.LLM_MODEL,
        "messages": _build_messages(history=history, user_message=user_message),
    }
    response = _post_json(
        url=f"{base_url}/chat/completions",
        payload=payload,
        headers=_build_headers(),
        timeout=config.LLM_TIMEOUT_SECONDS,
    )
    reply = _extract_reply_text(response).strip()
    if not reply:
        raise LLMServiceError("LLM reply is empty.")
    return reply


def _build_messages(*, history: list[dict[str, Any]], user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_prompt = get_system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        stripped = content.strip() if isinstance(content, str) else ""
        if role in {"user", "assistant", "system"} and stripped:
            messages.append({"role": role, "content": stripped})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    return headers


def _post_json(*, url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LLMServiceError(
            f"LLM request failed with HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise LLMServiceError("LLM response is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise LLMServiceError("LLM response body must be a JSON object.")
    return data


def _extract_reply_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMServiceError("LLM response does not contain choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LLMServiceError("LLM response choice is invalid.")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise LLMServiceError("LLM response does not contain a message object.")

    return _normalize_content(message.get("content"))


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)

    return ""
