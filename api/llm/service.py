from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from api import config
from api.llm.prompt import get_system_prompt


class LLMServiceError(RuntimeError):
    """Raised when the OpenAI-compatible LLM endpoint cannot provide a reply."""


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
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    reply = _extract_content(response.content)
    if not reply:
        raise LLMServiceError("LLM reply is empty.")
    return reply


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
