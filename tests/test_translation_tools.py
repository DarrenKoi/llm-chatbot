"""번역 도구의 회귀 동작을 검증한다."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from api.llm.service import LLMServiceError
from api.mcp import local_tools
from api.mcp import registry as mcp_registry
from api.workflows.translator.llm_decision import TranslationTurnDecision
from api.workflows.translator.tools import _translate as translate_tool
from api.workflows.translator.translation_engine import translate_text
from devtools.workflows.translator_example import build_lg_graph as build_translator_example_graph


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
    monkeypatch.setattr(
        "devtools.workflows.translator_example.lg_graph.decide_translation_turn",
        lambda **kwargs: TranslationTurnDecision(
            action="translate",
            source_text=kwargs["source_text"],
            target_language=kwargs["target_language"],
        ),
    )
    graph = build_translator_example_graph().compile(checkpointer=MemorySaver())

    result = graph.invoke(
        {
            "user_id": "dev-user",
            "workflow_id": "translator_example",
            "user_message": "ignored",
            "source_text": "How are you?",
            "target_language": "ja",
        },
        {"configurable": {"thread_id": "translator-example-error"}},
    )

    assert "LLM 번역 설정" in result["messages"][-1].content
    assert result["translated"] == ""
