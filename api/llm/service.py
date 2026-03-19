from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from api import config


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
    reply = _extract_reply_text(response)
    if not reply.strip():
        raise LLMServiceError("LLM reply is empty.")
    return reply.strip()


def _build_messages(*, history: list[dict[str, Any]], user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_prompt = config.LLM_SYSTEM_PROMPT.strip()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _build_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    return headers


def _post_json(*, url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(url, data=request_body, headers=headers, method="POST")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            raw_body = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMServiceError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise LLMServiceError(f"LLM request failed: {exc.reason}") from exc

    try:
        data = json.loads(raw_body.decode("utf-8"))
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
