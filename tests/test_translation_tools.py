"""번역 도구의 회귀 동작을 검증한다."""

import pytest

from api.llm.service import LLMServiceError
from api.mcp import local_tools
from api.mcp import registry as mcp_registry
from api.workflows.translator.tools import _translate as translate_tool
from api.workflows.translator.translation_engine import translate_text
from devtools.workflows.translator_example.graph import build_graph as build_translator_example_graph
from devtools.workflows.translator_example.nodes import translate_node as translate_example_node
from devtools.workflows.translator_example.state import TranslatorExampleState


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


def test_translator_example_returns_explicit_error_when_llm_fails(monkeypatch):
    def _raise_llm_error(**kwargs):
        raise LLMServiceError("endpoint unavailable")

    monkeypatch.setattr("api.workflows.translator.translation_engine.generate_json_reply", _raise_llm_error)
    build_translator_example_graph()

    state = TranslatorExampleState(
        user_id="dev-user",
        workflow_id="translator_example",
        node_id="translate",
        source_text="How are you?",
        target_language="ja",
    )

    result = translate_example_node(state, "ignored")

    assert result.action == "complete"
    assert result.next_node_id == "entry"
    assert "LLM 번역 설정" in result.reply
    assert result.data_updates["translated"] == ""
