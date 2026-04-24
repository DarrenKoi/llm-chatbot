"""번역 도구의 회귀 동작을 검증한다."""

import pytest

from api.mcp import local_tools
from api.mcp import registry as mcp_registry
from api.workflows.translator.tools import _translate as translate_tool
from api.workflows.translator.translation_engine import translate_text


@pytest.fixture(autouse=True)
def _clean_mcp():
    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()
    yield
    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()


def test_translate_text_uses_llm_for_unknown_phrase(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.translation_engine.generate_json_reply",
        lambda **kwargs: {
            "result": "お元気ですか？",
            "pronunciation_ko": "오겡키데스카",
        },
    )

    result = translate_text("How are you?", "ja")

    assert result["source"] == "en"
    assert result["target"] == "ja"
    assert result["result"] == "お元気ですか？"
    assert result["pronunciation_ko"] == "오겡키데스카"


def test_translate_text_returns_korean_pronunciation_for_english_dictionary_hit():
    result = translate_text("안녕하세요", "en")

    assert result["result"] == "Hello"
    assert result["pronunciation_ko"] == "헬로"


def test_translate_text_returns_llm_pronunciation_for_chinese(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.translation_engine.generate_json_reply",
        lambda **kwargs: {
            "result": "你好",
            "pronunciation_ko": "니하오",
        },
    )

    result = translate_text("안녕하세요", "중국어")

    assert result["source"] == "ko"
    assert result["target"] == "zh"
    assert result["result"] == "你好"
    assert result["pronunciation_ko"] == "니하오"


def test_translate_tool_no_longer_returns_placeholder(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.translation_engine.generate_json_reply",
        lambda **kwargs: {
            "result": "お元気ですか？",
            "pronunciation_ko": "오겡키데스카",
        },
    )

    result = translate_tool("How are you?", "ja")

    assert result["result"] == "お元気ですか？"
    assert "[Translated to JA]" not in result["result"]
