import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api import config
from api.cube.intents import ChoiceIntent, ReplyIntent, TableIntent, TextIntent
from api.llm.prompt import DEFAULT_SYSTEM_PROMPT, get_system_prompt
from api.llm.service import (
    _UNPARSEABLE_REPLY_INTENT_FALLBACK_TEXT,
    LLMServiceError,
    _build_messages,
    _extract_content,
    generate_json_reply,
    generate_reply_intent,
)


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


def _stub_llm_env(monkeypatch):
    monkeypatch.setattr("api.config.LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setattr("api.config.LLM_MODEL", "gpt-test")


def test_generate_reply_intent_uses_structured_output_when_supported(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.return_value = ReplyIntent(
        blocks=[
            TextIntent(text="형식을 골라주세요."),
            ChoiceIntent(
                question="형식",
                options=[{"label": "PDF", "value": "pdf"}, {"label": "엑셀", "value": "xlsx"}],
                processid="SelectFormat",
            ),
        ]
    )
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="PDF로 받을까요 엑셀로 받을까요?")

    assert isinstance(intent, ReplyIntent)
    assert intent.blocks[0].kind == "text"
    assert intent.blocks[1].kind == "choice"
    mock_llm.invoke.assert_not_called()
    mock_llm.with_structured_output.assert_called_once_with(ReplyIntent, method="function_calling")


def test_generate_reply_intent_parses_bare_json_without_fences(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("structured output failed")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(
        content='{"blocks":[{"kind":"text","text":"안녕"},{"kind":"table","headers":["a"],"rows":[["1"]]}]}'
    )
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="표 보여줘")

    assert [block.kind for block in intent.blocks] == ["text", "table"]


def test_generate_reply_intent_parses_blocks_assignment_as_structured_intent(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("structured output failed")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(
        content='blocks=[{"kind":"table","tilte":"오타는 무시","headers":["항목"],"rows":[["값"]]}]'
    )
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="표 보여줘")

    assert len(intent.blocks) == 1
    assert isinstance(intent.blocks[0], TableIntent)
    assert intent.blocks[0].headers == ["항목"]
    assert intent.blocks[0].rows == [["값"]]


def test_generate_reply_intent_parses_text_only_blocks_assignment_as_text_intent(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("structured output failed")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(content='blocks=[{"kind":"text","text":"multiMessage로 보낼 답변"}]')
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="간단히 답해줘")

    assert intent.blocks == [TextIntent(text="multiMessage로 보낼 답변")]


def test_generate_reply_intent_repairs_loose_blocks_assignment_keys(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("structured output failed")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(
        content='blocks=[{kind:"table", tilte:"오타는 무시", headers:["항목"], rows:[["값"]]}]'
    )
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="표 보여줘")

    assert len(intent.blocks) == 1
    assert isinstance(intent.blocks[0], TableIntent)
    assert intent.blocks[0].headers == ["항목"]
    assert intent.blocks[0].rows == [["값"]]


def test_generate_reply_intent_falls_back_to_json_in_text(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("tool calling not supported")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(content='```json\n{"blocks":[{"kind":"text","text":"안녕하세요"}]}\n```')
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="안녕")

    assert intent.blocks == [TextIntent(text="안녕하세요")]


def test_generate_reply_intent_wraps_unparseable_text_as_text_intent(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("nope")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(content="평문 답변, JSON 아님")
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="아무거나")

    assert intent.blocks == [TextIntent(text="평문 답변, JSON 아님")]


def test_generate_reply_intent_does_not_show_unparseable_blocks_payload(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("nope")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.return_value = mocker.Mock(content='blocks=[{"kind:"table", "tilte", ..}]')
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    intent = generate_reply_intent(history=[], user_message="표 보여줘")

    assert intent.blocks == [TextIntent(text=_UNPARSEABLE_REPLY_INTENT_FALLBACK_TEXT)]


def test_generate_reply_intent_raises_on_total_llm_failure(mocker, monkeypatch):
    _stub_llm_env(monkeypatch)

    structured_llm = mocker.Mock()
    structured_llm.invoke.side_effect = RuntimeError("structured failed")
    mock_llm = mocker.Mock()
    mock_llm.with_structured_output.return_value = structured_llm
    mock_llm.invoke.side_effect = RuntimeError("free-text invoke also failed")
    mocker.patch("api.llm.service._get_llm", return_value=mock_llm)

    with pytest.raises(LLMServiceError, match="LLM request failed"):
        generate_reply_intent(history=[], user_message="x")
