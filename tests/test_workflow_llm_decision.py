"""LLM decision helper regression tests for workflow controllers."""

from api.workflows.translator.llm_decision import decide_translation_turn


def test_translator_llm_decision_normalizes_language_and_translate(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "translate",
            "source_text": "감사합니다",
            "target_language": "english",
            "missing_slot": "",
            "reply": "",
        },
    )

    decision = decide_translation_turn(user_message='"감사합니다"를 영어로 번역해줘')

    assert decision.action == "translate"
    assert decision.source_text == "감사합니다"
    assert decision.target_language == "en"


def test_translator_llm_decision_accepts_canonical_language_code(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "translate",
            "source_text": "",
            "target_language": "en",
            "missing_slot": "",
            "reply": "",
        },
    )

    decision = decide_translation_turn(
        user_message="영어",
        source_text="감사합니다",
        last_asked_slot="target_language",
    )

    assert decision.action == "translate"
    assert decision.source_text == "감사합니다"
    assert decision.target_language == "en"


def test_translator_llm_decision_fills_default_question_when_reply_missing(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.translator.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "ask_user",
            "source_text": "안녕하세요",
            "target_language": "",
            "missing_slot": "target_language",
            "reply": "",
        },
    )

    decision = decide_translation_turn(user_message="번역해줘")

    assert decision.action == "ask_user"
    assert decision.missing_slot == "target_language"
    assert "어떤 언어로 번역할까요?" in decision.reply
