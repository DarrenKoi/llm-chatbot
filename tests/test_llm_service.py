from api import config
from api.llm.prompt import DEFAULT_SYSTEM_PROMPT, get_system_prompt
from api.llm.service import _build_messages, _extract_reply_text


def test_build_messages_includes_system_prompt_and_history(monkeypatch):
    monkeypatch.setattr("api.llm.service.get_system_prompt", lambda: "system prompt")

    messages = _build_messages(
        history=[
            {"role": "assistant", "content": "이전 답변"},
            {"role": "user", "content": "이전 질문"},
            {"role": "tool", "content": "skip"},
        ],
        user_message="현재 질문",
    )

    assert messages == [
        {"role": "system", "content": "system prompt"},
        {"role": "assistant", "content": "이전 답변"},
        {"role": "user", "content": "이전 질문"},
        {"role": "user", "content": "현재 질문"},
    ]


def test_get_system_prompt_returns_default_prompt(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT_OVERRIDE", "")
    monkeypatch.setattr("api.llm.prompt.system._build_time_context", lambda now=None: "현재 시각 문맥")

    assert get_system_prompt() == f"{DEFAULT_SYSTEM_PROMPT}\n\n현재 시각 문맥"


def test_get_system_prompt_uses_override(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT_OVERRIDE", "custom prompt")
    monkeypatch.setattr("api.llm.prompt.system._build_time_context", lambda now=None: "현재 시각 문맥")

    assert get_system_prompt() == "custom prompt\n\n현재 시각 문맥"


def test_build_time_context_uses_korean_local_time(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from api.llm.prompt.system import _build_time_context

    monkeypatch.setattr(config, "LLM_TIMEZONE", "Asia/Seoul")

    context = _build_time_context(datetime(2026, 4, 2, 9, 30, 15, tzinfo=ZoneInfo("UTC")))

    assert "2026-04-02 18:30:15" in context
    assert "Asia/Seoul" in context
    assert "UTC+09:00" in context


def test_extract_reply_text_supports_string_and_list_content():
    assert _extract_reply_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "안녕"},
                            {"type": "text", "text": "하세요"},
                        ]
                    }
                }
            ]
        }
    ) == "안녕하세요"
