from api import config
from api.llm.service import _build_messages, _extract_reply_text


def test_build_messages_includes_system_prompt_and_history(monkeypatch):
    monkeypatch.setattr(config, "LLM_SYSTEM_PROMPT", "system prompt")

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
