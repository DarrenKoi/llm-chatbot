import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api import config
from api.llm.prompt import DEFAULT_SYSTEM_PROMPT, get_system_prompt
from api.llm.service import LLMServiceError, _build_messages, _extract_content, generate_json_reply


def test_build_messages_includes_system_prompt_and_history(monkeypatch):
    monkeypatch.setattr(
        "api.llm.service.get_system_prompt",
        lambda user_profile_text="": f"system prompt::{user_profile_text}",
    )

    messages = _build_messages(
        history=[
            {"role": "assistant", "content": "이전 답변"},
            {"role": "user", "content": "이전 질문"},
            {"role": "tool", "content": "skip"},
        ],
        user_message="현재 질문",
        user_profile_text="- 이름: 홍길동",
    )

    assert messages == [
        SystemMessage(content="system prompt::- 이름: 홍길동"),
        AIMessage(content="이전 답변"),
        HumanMessage(content="이전 질문"),
        HumanMessage(content="현재 질문"),
    ]


def test_get_system_prompt_returns_default_prompt(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT_OVERRIDE", "")
    monkeypatch.setattr("api.llm.prompt.system._build_time_context", lambda now=None: "현재 시각 문맥")

    assert get_system_prompt() == f"{DEFAULT_SYSTEM_PROMPT}\n\n현재 시각 문맥"


def test_get_system_prompt_uses_override(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT_OVERRIDE", "custom prompt")
    monkeypatch.setattr("api.llm.prompt.system._build_time_context", lambda now=None: "현재 시각 문맥")

    assert get_system_prompt() == "custom prompt\n\n현재 시각 문맥"


def test_get_system_prompt_appends_profile_context(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT_OVERRIDE", "")
    monkeypatch.setattr("api.llm.prompt.system._build_time_context", lambda now=None: "현재 시각 문맥")

    prompt = get_system_prompt(user_profile_text="- 이름: 홍길동")

    assert prompt == (
        f"{DEFAULT_SYSTEM_PROMPT}\n\n"
        "현재 시각 문맥\n\n"
        "[사용자 프로필]\n"
        "- 이름: 홍길동\n\n"
        "이 사용자의 소속과 근무 맥락을 고려해 적절한 workflow와 답변 방식을 선택하세요."
    )


def test_build_time_context_uses_korean_local_time(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from api.llm.prompt.system import _build_time_context

    monkeypatch.setattr(config, "LLM_TIMEZONE", "Asia/Seoul")

    context = _build_time_context(datetime(2026, 4, 2, 9, 30, 15, tzinfo=ZoneInfo("UTC")))

    assert "2026-04-02 18:30:15" in context
    assert "Asia/Seoul" in context
    assert "UTC+09:00" in context


def test_extract_content_supports_string_and_list():
    assert _extract_content("안녕하세요") == "안녕하세요"
    assert (
        _extract_content(
            [
                {"type": "text", "text": "안녕"},
                {"type": "text", "text": "하세요"},
            ]
        )
        == "안녕하세요"
    )
    assert _extract_content(None) == ""


def test_generate_json_reply_parses_json_object(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")

    mock_llm = mocker.Mock()
    mock_llm.invoke.return_value = mocker.Mock(content='{"action":"translate","target_language":"en"}')
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    payload = generate_json_reply(system_prompt="system", user_prompt="user")

    assert payload == {"action": "translate", "target_language": "en"}


def test_generate_json_reply_accepts_fenced_json(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")

    mock_llm = mocker.Mock()
    mock_llm.invoke.return_value = mocker.Mock(content='```json\n{"action":"ask_user"}\n```')
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    payload = generate_json_reply(system_prompt="system", user_prompt="user")

    assert payload == {"action": "ask_user"}


def test_generate_json_reply_raises_for_invalid_json(mocker, monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")

    mock_llm = mocker.Mock()
    mock_llm.invoke.return_value = mocker.Mock(content="not json")
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    with pytest.raises(LLMServiceError, match="LLM JSON reply is invalid"):
        generate_json_reply(system_prompt="system", user_prompt="user")
