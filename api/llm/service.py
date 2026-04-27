import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from api import config
from api.cube.intents import ReplyIntent, TextIntent
from api.llm.prompt import get_system_prompt

logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when the OpenAI-compatible LLM endpoint cannot provide a reply."""


_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def generate_reply(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    user_profile_text: str = "",
) -> str:
    llm = _get_llm()
    messages = _build_messages(
        history=history,
        user_message=user_message,
        user_profile_text=user_profile_text,
    )
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM 응답 생성 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    reply = _extract_content(response.content)
    if not reply:
        logger.error("LLM 응답이 비어 있음: model=%s", config.LLM_MODEL)
        raise LLMServiceError("LLM reply is empty.")
    return reply


def generate_reply_intent(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    user_profile_text: str = "",
) -> ReplyIntent:
    """LLM에게 ``ReplyIntent`` 형태의 응답을 요청한다.

    1) ``with_structured_output``으로 Pydantic 스키마 강제. 도구 호출이 가능한
       모델은 여기서 끝난다.
    2) 실패 시 평문 응답에서 JSON 블록을 정규식으로 추출해 검증.
    3) 둘 다 실패하면 평문 전체를 단일 ``TextIntent``로 감싸 반환 — 어떤 경우에도
       사용자에게 응답이 가도록 보장한다.
    """

    llm = _get_llm()
    messages = _build_messages(
        history=history,
        user_message=user_message,
        user_profile_text=user_profile_text,
    )

    try:
        structured = llm.with_structured_output(ReplyIntent, method="function_calling").invoke(messages)
    except Exception:
        logger.warning("structured output 실패, 평문 fallback으로 전환", exc_info=True)
    else:
        if isinstance(structured, ReplyIntent):
            return structured

    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM 응답 생성 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    raw_text = _extract_content(response.content)
    if not raw_text:
        raise LLMServiceError("LLM reply is empty.")

    parsed = _parse_reply_intent_from_text(raw_text)
    if parsed is not None:
        return parsed

    return ReplyIntent(blocks=[TextIntent(text=raw_text)])


def _parse_reply_intent_from_text(raw_text: str) -> ReplyIntent | None:
    """평문 응답에서 ReplyIntent JSON을 best-effort로 추출한다."""
    stripped = raw_text.strip()
    candidates: list[str] = []

    fenced = _JSON_BLOCK_PATTERN.search(raw_text)
    if fenced:
        candidates.append(fenced.group(1).strip())

    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    else:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            candidates.append(stripped[start : end + 1])

    for candidate in dict.fromkeys(candidates):
        try:
            return ReplyIntent.model_validate_json(candidate)
        except ValidationError:
            continue

    if candidates:
        logger.warning("JSON-in-text ReplyIntent 검증 실패, 텍스트 fallback")
    return None


def generate_json_reply(
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """Call the configured LLM and parse a single JSON object reply."""

    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=user_prompt.strip()),
    ]
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM JSON 응답 생성 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    raw_reply = _extract_content(response.content)
    if not raw_reply:
        logger.error("LLM JSON 응답이 비어 있음: model=%s", config.LLM_MODEL)
        raise LLMServiceError("LLM JSON reply is empty.")

    try:
        return _extract_json_object(raw_reply)
    except ValueError as exc:
        logger.exception("LLM JSON 파싱 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM JSON reply is invalid: {exc}") from exc


def _get_llm() -> ChatOpenAI:
    base_url = config.LLM_BASE_URL.rstrip("/")
    if not base_url:
        raise LLMServiceError("LLM_BASE_URL is not configured.")
    if not config.LLM_MODEL:
        raise LLMServiceError("LLM_MODEL is not configured.")

    return ChatOpenAI(
        base_url=base_url,
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY or "not-needed",
        timeout=config.LLM_TIMEOUT_SECONDS,
    )


def _build_messages(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    user_profile_text: str = "",
) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    system_prompt = get_system_prompt(user_profile_text=user_profile_text)
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        stripped = content.strip() if isinstance(content, str) else ""
        if not stripped:
            continue
        if role == "user":
            messages.append(HumanMessage(content=stripped))
        elif role == "assistant":
            messages.append(AIMessage(content=stripped))
        elif role == "system":
            messages.append(SystemMessage(content=stripped))

    messages.append(HumanMessage(content=user_message.strip()))
    return messages


def _extract_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()

    return ""


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()

    match = _JSON_BLOCK_PATTERN.search(stripped)
    if match:
        stripped = match.group(1).strip()
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("expected a JSON object") from exc

    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload
