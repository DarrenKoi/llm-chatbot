"""번역 도구에서 공용으로 사용하는 번역 엔진."""

import json
import logging
import re

from api.llm.service import LLMServiceError, generate_json_reply

log = logging.getLogger(__name__)

_KOREAN_CHAR = re.compile(r"[\uac00-\ud7a3]")
_JAPANESE_CHAR = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf]")
_LANGUAGE_ALIASES = {
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
_JAPANESE_PRONUNCIATIONS_KO = {
    "こんにちは": "곤니치와",
    "ありがとうございます": "아리가토고자이마스",
}
_TRANSLATION_SYSTEM_PROMPT = """
당신은 번역 전용 엔진입니다.
주어진 source_text만 target_language로 번역하고 반드시 JSON 객체 하나만 반환하세요.

허용 키:
- result: 번역 결과 문자열
- pronunciation_ko: 일본어 번역일 때만 한국어 발음을 적고, 아니면 빈 문자열

규칙:
- 설명, 인사, 따옴표, 코드블록 없이 JSON만 반환
- 의미를 유지하되 자연스러운 번역을 사용
- 사람 이름, 제품명, URL, 코드 식별자는 필요할 때만 번역
- target_language가 ja가 아니면 pronunciation_ko는 반드시 빈 문자열
""".strip()


def normalize_language(language: str) -> str:
    return _LANGUAGE_ALIASES.get(language.strip().lower(), "")


def detect_language(text: str) -> str:
    if _KOREAN_CHAR.search(text):
        return "ko"
    if _JAPANESE_CHAR.search(text):
        return "ja"
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
    if translated is None:
        translated = _translate_with_llm(
            text=stripped_text,
            source_language=source_language,
            target_language=normalized_target,
        )

    return _build_result(
        source_language=source_language,
        target_language=normalized_target,
        translated=translated,
    )


def _translate_with_dictionary(*, text: str, source_language: str, target_language: str) -> str | None:
    dictionary = _TRANSLATIONS.get((source_language, target_language), {})
    lookup_key = text.lower() if source_language == "en" else text
    return dictionary.get(lookup_key)


def _translate_with_llm(*, text: str, source_language: str, target_language: str) -> str:
    payload = {
        "source_language": source_language,
        "target_language": target_language,
        "source_text": text,
    }
    try:
        raw_reply = generate_json_reply(
            system_prompt=_TRANSLATION_SYSTEM_PROMPT,
            user_prompt=f"다음 JSON 입력을 번역하세요.\n{json.dumps(payload, ensure_ascii=False)}",
        )
    except LLMServiceError as exc:
        log.exception("translator LLM fallback failed")
        raise ValueError("번역 결과를 생성하지 못했습니다. LLM 번역 설정을 확인한 뒤 다시 시도해주세요.") from exc

    translated = str(raw_reply.get("result", "")).strip()
    if not translated:
        raise ValueError("번역 결과를 생성하지 못했습니다. 잠시 후 다시 시도해주세요.")
    return translated


def _build_result(*, source_language: str, target_language: str, translated: str) -> dict[str, str]:
    result = {
        "source": source_language,
        "target": target_language,
        "result": translated,
    }
    pronunciation_ko = _get_korean_pronunciation(text=translated, language=target_language)
    if pronunciation_ko:
        result["pronunciation_ko"] = pronunciation_ko
    return result


def _get_korean_pronunciation(*, text: str, language: str) -> str:
    if language != "ja":
        return ""
    return _JAPANESE_PRONUNCIATIONS_KO.get(text.strip(), "")
