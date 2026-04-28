"""번역 도구에서 공용으로 사용하는 번역 엔진."""

import json
import logging
import re
from dataclasses import dataclass

from api.llm.service import LLMServiceError, generate_json_reply
from api.workflows.translator.prompts import (
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_USER_PROMPT_PREFIX,
)

log = logging.getLogger(__name__)

_KOREAN_CHAR = re.compile(r"[\uac00-\ud7a3]")
_HIRAGANA_KATAKANA = re.compile(r"[\u3040-\u30ff]")
_CJK_IDEOGRAPHS = re.compile(r"[\u4e00-\u9faf]")
LANGUAGE_ALIASES = {
    "english": "en",
    "eng": "en",
    "en": "en",
    "영어": "en",
    "japanese": "ja",
    "japan": "ja",
    "ja": "ja",
    "일본어": "ja",
    "일어": "ja",
    "korean": "ko",
    "kor": "ko",
    "ko": "ko",
    "한국어": "ko",
    "한글": "ko",
    "chinese": "zh",
    "mandarin": "zh",
    "zh": "zh",
    "zh-cn": "zh",
    "중국어": "zh",
    "중국말": "zh",
    "중어": "zh",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "es": "es",
    "스페인어": "es",
    "서반아어": "es",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "fr": "fr",
    "프랑스어": "fr",
    "불어": "fr",
    "german": "de",
    "deutsch": "de",
    "de": "de",
    "독일어": "de",
    "독어": "de",
    "vietnamese": "vi",
    "vi": "vi",
    "베트남어": "vi",
    "월남어": "vi",
    "thai": "th",
    "th": "th",
    "태국어": "th",
    "타이어": "th",
}
_TRANSLATIONS: dict[tuple[str, str], dict[str, str]] = {
    ("ko", "en"): {
        "안녕하세요": "Hello",
        "감사합니다": "Thank you",
    },
    ("ko", "ja"): {
        "안녕하세요": "こんにちは",
        "감사합니다": "ありがとうございます",
    },
    ("en", "ko"): {
        "hello": "안녕하세요",
        "thank you": "감사합니다",
    },
    ("en", "ja"): {
        "hello": "こんにちは",
        "thank you": "ありがとうございます",
    },
    ("ja", "en"): {
        "こんにちは": "Hello",
        "ありがとうございます": "Thank you",
    },
    ("ja", "ko"): {
        "こんにちは": "안녕하세요",
        "ありがとうございます": "감사합니다",
    },
}
_DICTIONARY_PRONUNCIATIONS_KO: dict[tuple[str, str], str] = {
    ("ja", "こんにちは"): "곤니치와",
    ("ja", "ありがとうございます"): "아리가토고자이마스",
    ("en", "Hello"): "헬로",
    ("en", "Thank you"): "땡큐",
}


def normalize_language(language: str) -> str:
    return LANGUAGE_ALIASES.get(language.strip().lower(), "")


def detect_language(text: str) -> str:
    if _KOREAN_CHAR.search(text):
        return "ko"
    if _HIRAGANA_KATAKANA.search(text):
        return "ja"
    if _CJK_IDEOGRAPHS.search(text):
        return "zh"
    return "en"


def translate_text(text: str, target_language: str) -> dict[str, str]:
    """입력 언어를 감지하고 대상 언어로 번역한다."""

    source_language = detect_language(text)
    normalized_target = normalize_language(target_language)
    if not normalized_target:
        raise ValueError("지원하지 않는 목표 언어입니다.")

    stripped_text = text.strip()
    if not stripped_text:
        raise ValueError("번역할 문장이 비어 있습니다.")

    if source_language == normalized_target:
        return _build_result(
            source_language=source_language,
            target_language=normalized_target,
            translated=stripped_text,
        )

    translated = _translate_with_dictionary(
        text=stripped_text,
        source_language=source_language,
        target_language=normalized_target,
    )
    pronunciation_ko = ""
    if translated is None:
        translated, pronunciation_ko = _translate_with_llm(
            text=stripped_text,
            source_language=source_language,
            target_language=normalized_target,
        )

    if normalized_target != "ko":
        dictionary_hit = _DICTIONARY_PRONUNCIATIONS_KO.get((normalized_target, translated.strip()), "")
        if dictionary_hit:
            pronunciation_ko = dictionary_hit

    return _build_result(
        source_language=source_language,
        target_language=normalized_target,
        translated=translated,
        pronunciation_ko=pronunciation_ko,
    )


def _translate_with_dictionary(*, text: str, source_language: str, target_language: str) -> str | None:
    dictionary = _TRANSLATIONS.get((source_language, target_language), {})
    lookup_key = text.lower() if source_language == "en" else text
    return dictionary.get(lookup_key)


def _translate_with_llm(*, text: str, source_language: str, target_language: str) -> tuple[str, str]:
    payload = {
        "source_language": source_language,
        "target_language": target_language,
        "source_text": text,
    }
    try:
        raw_reply = generate_json_reply(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=TRANSLATION_USER_PROMPT_PREFIX + json.dumps(payload, ensure_ascii=False),
        )
    except LLMServiceError as exc:
        log.exception("translator LLM fallback failed")
        raise ValueError("번역 결과를 생성하지 못했습니다. LLM 번역 설정을 확인한 뒤 다시 시도해주세요.") from exc

    translated = str(raw_reply.get("result", "")).strip()
    if not translated:
        raise ValueError("번역 결과를 생성하지 못했습니다. 잠시 후 다시 시도해주세요.")
    pronunciation_ko = str(raw_reply.get("pronunciation_ko", "")).strip()
    return translated, pronunciation_ko


def _build_result(
    *,
    source_language: str,
    target_language: str,
    translated: str,
    pronunciation_ko: str = "",
) -> dict[str, str]:
    result = {
        "source": source_language,
        "target": target_language,
        "result": translated,
    }
    if pronunciation_ko:
        result["pronunciation_ko"] = pronunciation_ko
    return result


@dataclass
class TranslationResult:
    success: bool
    translated: str = ""
    source_language: str = ""
    direction: str = ""
    pronunciation_ko: str = ""
    reply: str = ""
    error: str = ""


def execute_translation(source_text: str, target_language: str, *, tool_id: str = "translate") -> TranslationResult:
    """MCP translate 도구를 호출하고 정규화된 결과를 반환한다."""

    from api.mcp_client.executor import execute_tool_call
    from api.mcp_client.models import MCPToolCall

    log.info("[translator] %s 도구 호출: text=%s target_language=%s", tool_id, source_text, target_language)
    result = execute_tool_call(
        MCPToolCall(
            tool_id=tool_id,
            arguments={"text": source_text, "target_language": target_language},
        )
    )
    log.info("[translator] %s 도구 결과: %s", tool_id, result)

    if not result.success:
        return TranslationResult(
            success=False,
            error=result.error or "번역 중 오류가 발생했습니다.",
        )

    translated = result.output.get("result", "") if isinstance(result.output, dict) else ""
    source_language = ""
    direction = ""
    pronunciation_ko = ""
    if isinstance(result.output, dict):
        source_language = result.output.get("source", "")
        direction = f"{source_language}\u2192{result.output.get('target', '')}"
        pronunciation_ko = result.output.get("pronunciation_ko", "")

    reply = translated
    if pronunciation_ko:
        reply = f"{translated}\n(한국어 발음: {pronunciation_ko})"

    return TranslationResult(
        success=True,
        translated=translated,
        source_language=source_language,
        direction=direction,
        pronunciation_ko=pronunciation_ko,
        reply=reply,
    )
