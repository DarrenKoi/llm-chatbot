"""샘플 번역 워크플로에서 사용하는 MCP 도구를 등록한다."""

import re

from api.mcp.local_tools import register_handler
from api.mcp.models import MCPServerConfig, MCPTool
from api.mcp.registry import register_server, register_tool

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

# ---------------------------------------------------------------------------
# 스텁 번역 사전 (테스트·데모용)
# ---------------------------------------------------------------------------

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


def _normalize_language(language: str) -> str:
    return _LANGUAGE_ALIASES.get(language.strip().lower(), "")


def _detect_language(text: str) -> str:
    if _KOREAN_CHAR.search(text):
        return "ko"
    if _JAPANESE_CHAR.search(text):
        return "ja"
    return "en"


def _translate(text: str, target_language: str) -> dict[str, str]:
    """입력 언어를 감지하고 대상 언어로 번역한다."""

    source_language = _detect_language(text)
    normalized_target = _normalize_language(target_language)
    if not normalized_target:
        raise ValueError("지원하지 않는 목표 언어입니다.")

    if source_language == normalized_target:
        return {"source": source_language, "target": normalized_target, "result": text}

    dictionary = _TRANSLATIONS.get((source_language, normalized_target), {})
    lookup_key = text.strip().lower() if source_language == "en" else text.strip()
    translated = dictionary.get(lookup_key)
    if translated is None:
        translated = f"[Translated to {normalized_target.upper()}] {text.strip()}"

    return {
        "source": source_language,
        "target": normalized_target,
        "result": translated,
    }


def register_sample_tools() -> None:
    """샘플 MCP 서버·도구·핸들러를 등록한다."""

    server = MCPServerConfig(server_id="sample_local", endpoint="local://sample")
    register_server(server)

    register_tool(MCPTool(
        tool_id="translate",
        server_id="sample_local",
        description="한국어/영어/일본어 사이의 번역을 수행한다.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "target_language": {"type": "string"},
            },
            "required": ["text", "target_language"],
        },
    ))

    register_handler("translate", _translate)
