import ast
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from api import config
from api.cube.intents import ReplyIntent, TextIntent
from api.llm.prompt import get_system_prompt
from api.logging_service import get_topic_logger

logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when the OpenAI-compatible LLM endpoint cannot provide a reply."""


_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_FENCED_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_BLOCKS_ASSIGNMENT_PATTERN = re.compile(r"\bblocks\s*=\s*", re.IGNORECASE)
_BARE_OBJECT_KEY_PATTERN = re.compile(r"([{\[,]\s*)([A-Za-z_][A-Za-z0-9_-]*)\s*:")
_MISQUOTED_OBJECT_KEY_PATTERN = re.compile(r'([{\[,]\s*)"([A-Za-z_][A-Za-z0-9_-]*):"')
_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
_PYTHON_HEX_ESCAPE_PATTERN = re.compile(r"\\x([0-9A-Fa-f]{2})")
_INTENT_SHAPED_TEXT_PATTERN = re.compile(r"""(?ix)(["']?blocks["']?\s*[:=]|["']?kind["']?\s*:)""")
_UNPARSEABLE_REPLY_INTENT_FALLBACK_TEXT = "응답 형식이 올바르지 않아 내용을 표시하지 못했습니다. 다시 요청해 주세요."
_LLM_LOG_RAW_TEXT_MAX_CHARS = 12000
_LLM_LOG_CANDIDATE_MAX_CHARS = 1200
_LLM_LOG_CONTENT_MAX_CHARS = 500


@dataclass(slots=True)
class LLMHealthResult:
    """LLM API 헬스체크 결과."""

    ok: bool
    status: str  # "alive" | "not configured" | "failed"
    detail: str
    model: str
    base_url: str
    latency_ms: int | None


def check_llm_health(*, timeout_seconds: int | None = None) -> LLMHealthResult:
    """LLM API가 실제로 응답하는지 가벼운 호출로 점검한다.

    설정 누락이면 즉시 ``not configured``를 반환하고, 그 외에는 짧은 프롬프트를
    한 번 호출해 응답 여부와 왕복 지연(latency)을 측정한다. 예외는 잡아서
    ``failed`` 결과로 변환하므로 호출 측에서 별도 try/except가 필요 없다.
    """
    base_url = config.LLM_BASE_URL.rstrip("/")
    if not base_url or not config.LLM_MODEL:
        return LLMHealthResult(
            ok=False,
            status="not configured",
            detail="LLM_BASE_URL 또는 LLM_MODEL이 설정되지 않았습니다.",
            model=config.LLM_MODEL,
            base_url=base_url,
            latency_ms=None,
        )

    probe_timeout = timeout_seconds if timeout_seconds is not None else config.LLM_HEALTHCHECK_TIMEOUT_SECONDS
    llm = ChatOpenAI(
        base_url=base_url,
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY or "not-needed",
        timeout=probe_timeout,
        max_retries=0,
    )

    started_at = time.monotonic()
    try:
        response = llm.invoke([HumanMessage(content="ping")])
    except Exception as exc:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        return LLMHealthResult(
            ok=False,
            status="failed",
            detail=f"LLM 응답 점검 실패: {exc}",
            model=config.LLM_MODEL,
            base_url=base_url,
            latency_ms=latency_ms,
        )

    latency_ms = int((time.monotonic() - started_at) * 1000)
    reply = _extract_content(response.content)
    if not reply:
        return LLMHealthResult(
            ok=False,
            status="failed",
            detail="LLM이 빈 응답을 반환했습니다.",
            model=config.LLM_MODEL,
            base_url=base_url,
            latency_ms=latency_ms,
        )

    return LLMHealthResult(
        ok=True,
        status="alive",
        detail=f"LLM API가 {latency_ms}ms 만에 정상 응답했습니다.",
        model=config.LLM_MODEL,
        base_url=base_url,
        latency_ms=latency_ms,
    )


def generate_reply(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    user_profile_text: str = "",
    user_id: str = "",
    conversation_id: str = "",
) -> str:
    llm = _get_llm()
    messages = _build_messages(
        history=history,
        user_message=user_message,
        user_profile_text=user_profile_text,
    )
    started_at = time.monotonic()
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        logger.exception("LLM 응답 생성 실패: model=%s", config.LLM_MODEL)
        _log_llm_interaction(
            function="generate_reply",
            status="error",
            path="plain",
            latency_ms=latency_ms,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            history_len=len(history),
            error=str(exc),
        )
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    latency_ms = int((time.monotonic() - started_at) * 1000)
    reply = _extract_content(response.content)
    if not reply:
        logger.error("LLM 응답이 비어 있음: model=%s", config.LLM_MODEL)
        _log_llm_interaction(
            function="generate_reply",
            status="empty",
            path="plain",
            latency_ms=latency_ms,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            history_len=len(history),
            token_usage=_extract_token_usage(response),
        )
        raise LLMServiceError("LLM reply is empty.")
    logger.info("llm_reply model=%s text=%s", config.LLM_MODEL, json.dumps(reply, ensure_ascii=False))
    _log_llm_interaction(
        function="generate_reply",
        status="ok",
        path="plain",
        latency_ms=latency_ms,
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=user_message,
        response_text=reply,
        history_len=len(history),
        token_usage=_extract_token_usage(response),
    )
    return reply


def generate_reply_intent(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    user_profile_text: str = "",
    user_id: str = "",
    conversation_id: str = "",
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
    started_at = time.monotonic()

    def _emit(
        *,
        status: str,
        path: str,
        response_text: str = "",
        token_usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        _log_llm_interaction(
            function="generate_reply_intent",
            status=status,
            path=path,
            latency_ms=int((time.monotonic() - started_at) * 1000),
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            response_text=response_text,
            history_len=len(history),
            token_usage=token_usage,
            error=error,
        )

    try:
        structured = llm.with_structured_output(ReplyIntent, method="function_calling").invoke(messages)
    except Exception as exc:
        logger.warning("structured output 실패, 평문 fallback으로 전환", exc_info=True)
        _log_llm_reply_intent_diagnostic(
            "llm_reply_intent_structured_output_failed",
            path="structured_output_call",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
        )
    else:
        if isinstance(structured, ReplyIntent) and _has_usable_content(structured):
            logger.info(
                "llm_reply_intent path=structured model=%s intent=%s",
                config.LLM_MODEL,
                json.dumps(structured.model_dump(), ensure_ascii=False, default=str),
            )
            _emit(
                status="ok",
                path="structured",
                response_text=json.dumps(structured.model_dump(), ensure_ascii=False, default=str),
            )
            return structured
        logger.warning("structured output이 빈 ReplyIntent를 반환, 평문 fallback으로 전환")

    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM 응답 생성 실패: model=%s", config.LLM_MODEL)
        _emit(status="error", path="raw_text", error=str(exc))
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    token_usage = _extract_token_usage(response)
    raw_text = _extract_content(response.content)
    if not raw_text:
        _emit(status="empty", path="raw_text", token_usage=token_usage)
        raise LLMServiceError("LLM reply is empty.")
    logger.info(
        "llm_reply_intent path=raw_text model=%s text=%s", config.LLM_MODEL, json.dumps(raw_text, ensure_ascii=False)
    )

    parsed = _parse_reply_intent_from_text(raw_text)
    if parsed is not None:
        if _has_usable_content(parsed):
            _log_llm_reply_intent_diagnostic(
                "llm_reply_intent_json_in_text_fallback",
                path="json_in_text",
                raw_text=raw_text,
                candidate_count=len(dict.fromkeys(_reply_intent_candidates(raw_text))),
                intent=parsed.model_dump(),
            )
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
            _emit(
                status="ok",
                path="json_in_text",
                response_text=raw_text,
                token_usage=token_usage,
            )
            return parsed

        _log_llm_reply_intent_diagnostic(
            "llm_reply_intent_unusable_json_in_text",
            path="unusable_json_in_text",
            raw_text=raw_text,
            candidate_count=len(dict.fromkeys(_reply_intent_candidates(raw_text))),
            intent=parsed.model_dump(),
            reason="empty_or_blank_reply_intent",
        )
        logger.warning(
            "llm_reply_intent_fallback path=unusable_json_in_text model=%s raw_text=%s intent=%s",
            config.LLM_MODEL,
            json.dumps(raw_text, ensure_ascii=False),
            json.dumps(parsed.model_dump(), ensure_ascii=False, default=str),
        )

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
    _emit(
        status="ok",
        path="text_fallback",
        response_text=fallback_text,
        token_usage=token_usage,
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
        _log_llm_reply_intent_diagnostic(
            "llm_reply_intent_invalid_json_in_text",
            path="invalid_json_in_text",
            raw_text=raw_text,
            candidate_count=len(dict.fromkeys(candidates)),
            candidate_diagnostics=_reply_intent_candidate_diagnostics(candidates),
        )
        logger.warning(
            "llm_reply_intent_fallback path=invalid_json_in_text model=%s candidate_count=%d raw_text=%s",
            config.LLM_MODEL,
            len(candidates),
            json.dumps(raw_text, ensure_ascii=False),
        )
    return None


def _log_llm_reply_intent_diagnostic(event: str, *, path: str, raw_text: str = "", **data: Any) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "path": path,
        "model": config.LLM_MODEL,
        **data,
    }
    if raw_text:
        raw_text_value, raw_text_truncated = _truncate_for_log(raw_text, _LLM_LOG_RAW_TEXT_MAX_CHARS)
        payload.update(
            raw_text=raw_text_value,
            raw_text_length=len(raw_text),
            raw_text_truncated=raw_text_truncated,
        )
    try:
        get_topic_logger("llm", json_output=True).warning(event, extra={"activity_data": payload})
    except Exception:
        logger.exception("LLM 진단 로그 기록 실패: event=%s path=%s model=%s", event, path, config.LLM_MODEL)


def _truncate_for_log(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _extract_token_usage(response: Any) -> dict[str, Any] | None:
    """LangChain 응답에서 토큰 사용량(input/output/total)을 best-effort로 뽑아낸다.

    ``with_structured_output`` 경로는 순수 Pydantic 객체를 돌려줘 usage가 없으므로
    그 경우 None을 반환한다.
    """
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict) and usage:
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return None


def _log_llm_interaction(
    *,
    function: str,
    status: str,
    path: str,
    latency_ms: int | None,
    user_id: str = "",
    conversation_id: str = "",
    user_message: str = "",
    response_text: str = "",
    history_len: int | None = None,
    token_usage: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """사용자↔LLM 상호작용 1건을 구조화된 JSONL 레코드로 ``logs/llm/llm.jsonl``에 남긴다.

    내용(user_message/response_text)은 ``_LLM_LOG_CONTENT_MAX_CHARS`` 기준으로 잘라
    저장하고, 원래 길이와 절단 여부를 함께 기록한다.
    """
    payload: dict[str, Any] = {
        "event": "llm_interaction",
        "function": function,
        "model": config.LLM_MODEL,
        "status": status,
        "path": path,
        "latency_ms": latency_ms,
    }
    if user_id:
        payload["user_id"] = user_id
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if history_len is not None:
        payload["history_len"] = history_len
    if token_usage:
        payload["token_usage"] = token_usage
    if user_message:
        text, truncated = _truncate_for_log(user_message, _LLM_LOG_CONTENT_MAX_CHARS)
        payload["user_message"] = text
        payload["user_message_len"] = len(user_message)
        payload["user_message_truncated"] = truncated
    if response_text:
        text, truncated = _truncate_for_log(response_text, _LLM_LOG_CONTENT_MAX_CHARS)
        payload["response_text"] = text
        payload["response_len"] = len(response_text)
        payload["response_truncated"] = truncated
    if error:
        payload["error"] = error
    try:
        get_topic_logger("llm", json_output=True).info("llm_interaction", extra={"activity_data": payload})
    except Exception:
        logger.exception("LLM interaction 로그 기록 실패: function=%s status=%s", function, status)


def _reply_intent_candidate_diagnostics(candidates: list[str]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, candidate in enumerate(dict.fromkeys(candidates), start=1):
        candidate_text, candidate_truncated = _truncate_for_log(candidate, _LLM_LOG_CANDIDATE_MAX_CHARS)
        variants = []
        for variant_index, variant in enumerate(dict.fromkeys(_reply_intent_candidate_variants(candidate)), start=1):
            variant_text, variant_truncated = _truncate_for_log(variant, _LLM_LOG_CANDIDATE_MAX_CHARS)
            variant_diagnostic: dict[str, Any] = {
                "variant_index": variant_index,
                "variant": variant_text,
                "variant_length": len(variant),
                "variant_truncated": variant_truncated,
            }
            payload = _load_jsonish(variant)
            if payload is None:
                variant_diagnostic["status"] = "jsonish_parse_failed"
                variants.append(variant_diagnostic)
                continue

            variant_diagnostic["payload_type"] = type(payload).__name__
            normalized = _normalize_reply_intent_payload(payload)
            if normalized is None:
                variant_diagnostic["status"] = "unsupported_reply_intent_shape"
                variants.append(variant_diagnostic)
                continue

            try:
                ReplyIntent.model_validate(normalized)
            except ValidationError as exc:
                variant_diagnostic["status"] = "reply_intent_validation_failed"
                variant_diagnostic["validation_errors"] = _validation_error_summary(exc)
            else:
                variant_diagnostic["status"] = "valid"
            variants.append(variant_diagnostic)

        diagnostics.append(
            {
                "candidate_index": index,
                "candidate": candidate_text,
                "candidate_length": len(candidate),
                "candidate_truncated": candidate_truncated,
                "variants": variants,
            }
        )
    return diagnostics


def _validation_error_summary(error: ValidationError) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in error.errors(include_input=False):
        summary.append(
            {
                "type": item.get("type"),
                "loc": item.get("loc"),
                "msg": item.get("msg"),
            }
        )
    return summary


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
    variants = _reply_intent_candidate_variants(candidate)

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


def _reply_intent_candidate_variants(candidate: str) -> list[str]:
    variants = [candidate]
    assignment_value = _extract_blocks_assignment_value(candidate)
    if assignment_value:
        variants.append(assignment_value)
        variants.append(f'{{"blocks": {assignment_value}}}')
    if candidate.strip().startswith("["):
        variants.append(f'{{"blocks": {candidate}}}')
    return variants


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


def _load_jsonish(text: str, *, _depth: int = 0) -> Any | None:
    for variant in _jsonish_variants(text):
        # 정상 JSON을 먼저 시도하고, 실패할 때만 strict=False로 fallback한다.
        # strict=False는 문자열 안의 이스케이프되지 않은 제어 문자(예: 멀티행 날씨 응답의 raw \n)를
        # 허용하지만 기본 파서보다 2배 이상 느려서 핫 패스에서 매번 쓰지 않는다.
        for loader in (json.loads, _json_loads_lenient, ast.literal_eval):
            try:
                payload = loader(variant)
            except (json.JSONDecodeError, SyntaxError, ValueError):
                continue
            if _depth == 0 and isinstance(payload, str):
                stripped = payload.strip()
                if stripped.startswith(("{", "[")):
                    # 일부 모델이 JSON 객체 전체를 따옴표로 감싸 문자열로 직렬화하는 케이스.
                    unwrapped = _load_jsonish(stripped, _depth=1)
                    if unwrapped is not None:
                        return unwrapped
                    continue
            return payload

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
        _repair_python_hex_escapes,
        _remove_trailing_commas,
        _repair_misquoted_object_keys,
        _quote_bare_object_keys,
        _remove_trailing_commas,
    ):
        current = transform(current)
        add(current)

    return variants


def _json_loads_lenient(value: str) -> Any:
    return json.loads(value, strict=False)


def _remove_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA_PATTERN.sub(r"\1", text)


def _repair_python_hex_escapes(text: str) -> str:
    # 일부 로컬 LLM이 날씨/기온 응답에서 ° 대신 Python 스타일 \xb0를 흘려보낸다.
    # JSON은 \x 이스케이프를 허용하지 않으므로 \u00HH 형태로 다시 써서 복구한다.
    return _PYTHON_HEX_ESCAPE_PATTERN.sub(lambda m: f"\\u00{m.group(1).lower()}", text)


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
    user_id: str = "",
    conversation_id: str = "",
) -> dict[str, Any]:
    """Call the configured LLM and parse a single JSON object reply."""

    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=user_prompt.strip()),
    ]
    started_at = time.monotonic()
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        logger.exception("LLM JSON 응답 생성 실패: model=%s", config.LLM_MODEL)
        _log_llm_interaction(
            function="generate_json_reply",
            status="error",
            path="json",
            latency_ms=int((time.monotonic() - started_at) * 1000),
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_prompt,
            error=str(exc),
        )
        raise LLMServiceError(f"LLM request failed: {exc}") from exc

    latency_ms = int((time.monotonic() - started_at) * 1000)
    token_usage = _extract_token_usage(response)
    raw_reply = _extract_content(response.content)
    if not raw_reply:
        logger.error("LLM JSON 응답이 비어 있음: model=%s", config.LLM_MODEL)
        _log_llm_interaction(
            function="generate_json_reply",
            status="empty",
            path="json",
            latency_ms=latency_ms,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_prompt,
            token_usage=token_usage,
        )
        raise LLMServiceError("LLM JSON reply is empty.")

    try:
        parsed = _extract_json_object(raw_reply)
    except ValueError as exc:
        logger.exception("LLM JSON 파싱 실패: model=%s", config.LLM_MODEL)
        _log_llm_interaction(
            function="generate_json_reply",
            status="invalid_json",
            path="json",
            latency_ms=latency_ms,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_prompt,
            response_text=raw_reply,
            token_usage=token_usage,
            error=str(exc),
        )
        raise LLMServiceError(f"LLM JSON reply is invalid: {exc}") from exc

    logger.info(
        "llm_json_reply model=%s payload=%s",
        config.LLM_MODEL,
        json.dumps(parsed, ensure_ascii=False, default=str),
    )
    _log_llm_interaction(
        function="generate_json_reply",
        status="ok",
        path="json",
        latency_ms=latency_ms,
        user_id=user_id,
        conversation_id=conversation_id,
        user_message=user_prompt,
        response_text=raw_reply,
        token_usage=token_usage,
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
