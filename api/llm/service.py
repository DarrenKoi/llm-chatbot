import ast
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
_FENCED_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_BLOCKS_ASSIGNMENT_PATTERN = re.compile(r"\bblocks\s*=\s*", re.IGNORECASE)
_BARE_OBJECT_KEY_PATTERN = re.compile(r"([{\[,]\s*)([A-Za-z_][A-Za-z0-9_-]*)\s*:")
_MISQUOTED_OBJECT_KEY_PATTERN = re.compile(r'([{\[,]\s*)"([A-Za-z_][A-Za-z0-9_-]*):"')
_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
_INTENT_SHAPED_TEXT_PATTERN = re.compile(r"""(?ix)(["']?blocks["']?\s*[:=]|["']?kind["']?\s*:)""")
_UNPARSEABLE_REPLY_INTENT_FALLBACK_TEXT = "응답 형식이 올바르지 않아 내용을 표시하지 못했습니다. 다시 요청해 주세요."


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
    logger.info("llm_reply model=%s text=%s", config.LLM_MODEL, json.dumps(reply, ensure_ascii=False))
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
        if isinstance(structured, ReplyIntent) and _has_usable_content(structured):
            logger.info(
                "llm_reply_intent path=structured model=%s intent=%s",
                config.LLM_MODEL,
                json.dumps(structured.model_dump(), ensure_ascii=False, default=str),
            )
            return structured
        logger.warning("structured output이 빈 ReplyIntent를 반환, 평문 fallback으로 전환")

    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM 응답 생성 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    raw_text = _extract_content(response.content)
    if not raw_text:
        raise LLMServiceError("LLM reply is empty.")
    logger.info(
        "llm_reply_intent path=raw_text model=%s text=%s", config.LLM_MODEL, json.dumps(raw_text, ensure_ascii=False)
    )

    parsed = _parse_reply_intent_from_text(raw_text)
    if parsed is not None and _has_usable_content(parsed):
        logger.warning(
            "llm_reply_intent_fallback path=json_in_text model=%s raw_text=%s intent=%s",
            config.LLM_MODEL,
            json.dumps(raw_text, ensure_ascii=False),
            json.dumps(parsed.model_dump(), ensure_ascii=False, default=str),
        )
        logger.info(
            "llm_reply_intent path=parsed_json model=%s intent=%s",
            config.LLM_MODEL,
            json.dumps(parsed.model_dump(), ensure_ascii=False, default=str),
        )
        return parsed

    if _looks_like_reply_intent_text(raw_text):
        logger.warning("LLM 응답이 ReplyIntent 형태였으나 검증에 실패해 안전한 안내 문구로 대체")
        fallback_text = _UNPARSEABLE_REPLY_INTENT_FALLBACK_TEXT
    else:
        fallback_text = raw_text

    fallback = ReplyIntent(blocks=[TextIntent(text=fallback_text)])
    logger.info(
        "llm_reply_intent path=text_fallback model=%s intent=%s",
        config.LLM_MODEL,
        json.dumps(fallback.model_dump(), ensure_ascii=False, default=str),
    )
    return fallback


def _has_usable_content(reply: ReplyIntent) -> bool:
    """ReplyIntent에 사용자에게 보낼 만한 내용이 하나라도 있는지 확인한다."""
    for block in reply.blocks:
        if isinstance(block, TextIntent):
            if block.text.strip():
                return True
        else:
            return True
    return False


def _parse_reply_intent_from_text(raw_text: str) -> ReplyIntent | None:
    """평문 응답에서 ReplyIntent JSON을 best-effort로 추출한다."""
    candidates = _reply_intent_candidates(raw_text)

    for candidate in dict.fromkeys(candidates):
        parsed = _parse_reply_intent_candidate(candidate)
        if parsed is not None:
            return parsed

    if candidates:
        logger.warning(
            "llm_reply_intent_fallback path=invalid_json_in_text model=%s candidate_count=%d raw_text=%s",
            config.LLM_MODEL,
            len(candidates),
            json.dumps(raw_text, ensure_ascii=False),
        )
    return None


def _looks_like_reply_intent_text(raw_text: str) -> bool:
    return bool(_INTENT_SHAPED_TEXT_PATTERN.search(raw_text))


def _reply_intent_candidates(raw_text: str) -> list[str]:
    stripped = raw_text.strip()
    candidates: list[str] = []

    def add(value: str | None) -> None:
        if value and (candidate := value.strip()):
            candidates.append(candidate)

    for fenced in _FENCED_BLOCK_PATTERN.finditer(raw_text):
        fenced_text = fenced.group(1).strip()
        add(fenced_text)
        add(_extract_blocks_assignment_value(fenced_text))

    add(stripped)
    add(_extract_blocks_assignment_value(stripped))

    if stripped.startswith("{") and stripped.endswith("}"):
        add(stripped)
    else:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            add(stripped[start : end + 1])

    if stripped.startswith("[") and stripped.endswith("]"):
        add(stripped)

    return candidates


def _parse_reply_intent_candidate(candidate: str) -> ReplyIntent | None:
    variants = [candidate]
    assignment_value = _extract_blocks_assignment_value(candidate)
    if assignment_value:
        variants.append(assignment_value)
        variants.append(f'{{"blocks": {assignment_value}}}')
    if candidate.strip().startswith("["):
        variants.append(f'{{"blocks": {candidate}}}')

    for variant in dict.fromkeys(variants):
        payload = _load_jsonish(variant)
        if payload is None:
            continue

        normalized = _normalize_reply_intent_payload(payload)
        if normalized is None:
            continue

        try:
            return ReplyIntent.model_validate(normalized)
        except ValidationError:
            continue

    return None


def _normalize_reply_intent_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        return {"blocks": payload}

    if not isinstance(payload, dict):
        return None

    blocks = payload.get("blocks")
    if isinstance(blocks, dict):
        normalized = dict(payload)
        normalized["blocks"] = [blocks]
        return normalized

    if "blocks" in payload:
        return payload

    if "kind" in payload:
        return {"blocks": [payload]}

    return None


def _load_jsonish(text: str) -> Any | None:
    for variant in _jsonish_variants(text):
        try:
            return json.loads(variant)
        except json.JSONDecodeError:
            pass

        try:
            return ast.literal_eval(variant)
        except (SyntaxError, ValueError):
            pass

    return None


def _jsonish_variants(text: str) -> list[str]:
    variants: list[str] = []

    def add(value: str) -> None:
        normalized = value.strip()
        if normalized and normalized not in variants:
            variants.append(normalized)

    current = text.strip()
    add(current)
    for transform in (
        _remove_trailing_commas,
        _repair_misquoted_object_keys,
        _quote_bare_object_keys,
        _remove_trailing_commas,
    ):
        current = transform(current)
        add(current)

    return variants


def _remove_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA_PATTERN.sub(r"\1", text)


def _repair_misquoted_object_keys(text: str) -> str:
    return _MISQUOTED_OBJECT_KEY_PATTERN.sub(r'\1"\2":"', text)


def _quote_bare_object_keys(text: str) -> str:
    return _BARE_OBJECT_KEY_PATTERN.sub(r'\1"\2":', text)


def _extract_blocks_assignment_value(text: str) -> str | None:
    match = _BLOCKS_ASSIGNMENT_PATTERN.search(text)
    if not match:
        return None

    index = match.end()
    while index < len(text) and text[index].isspace():
        index += 1

    if index >= len(text) or text[index] not in "[{":
        return None

    return _extract_balanced_jsonish_region(text, index)


def _extract_balanced_jsonish_region(text: str, start: int) -> str | None:
    pairs = {"[": "]", "{": "}"}
    stack = [pairs[text[start]]]
    quote: str | None = None
    escaped = False

    for index in range(start + 1, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
        elif char in pairs:
            stack.append(pairs[char])
        elif char in "]}":
            if not stack or stack[-1] != char:
                return None
            stack.pop()
            if not stack:
                return text[start : index + 1]

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
        parsed = _extract_json_object(raw_reply)
    except ValueError as exc:
        logger.exception("LLM JSON 파싱 실패: model=%s", config.LLM_MODEL)
        raise LLMServiceError(f"LLM JSON reply is invalid: {exc}") from exc

    logger.info(
        "llm_json_reply model=%s payload=%s",
        config.LLM_MODEL,
        json.dumps(parsed, ensure_ascii=False, default=str),
    )
    return parsed


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
