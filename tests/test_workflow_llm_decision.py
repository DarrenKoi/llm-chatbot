"""LLM decision helper regression tests for workflow controllers."""

from api.workflows.translator.llm_decision import decide_translation_turn
from api.workflows.travel_planner.llm_decision import CANCEL_GUIDE_REPLY, decide_travel_planner_turn


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
    assert "영어 또는 일본어" in decision.reply


def test_travel_planner_llm_decision_normalizes_values(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.travel_planner.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "recommend_destination",
            "destination": "",
            "travel_style": "힐링",
            "duration_text": "",
            "companion_type": "friends",
            "missing_slot": "",
            "reply": "",
        },
    )

    decision = decide_travel_planner_turn(user_message="힐링 여행 추천해줘")

    assert decision.action == "recommend_destination"
    assert decision.travel_style == "휴양"
    assert decision.duration_text == ""
    assert decision.companion_type == "친구"


def test_travel_planner_llm_decision_preserves_duration_on_recommend(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.travel_planner.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "recommend_destination",
            "destination": "",
            "travel_style": "휴양",
            "duration_text": "",
            "companion_type": "",
            "missing_slot": "",
            "reply": "",
        },
    )

    decision = decide_travel_planner_turn(
        user_message="휴양으로 여행 추천해줘",
        duration_text="2박 3일",
    )

    assert decision.action == "recommend_destination"
    assert decision.travel_style == "휴양"
    assert decision.duration_text == "2박 3일"


def test_travel_planner_llm_decision_fills_default_duration_question(monkeypatch):
    monkeypatch.setattr(
        "api.workflows.travel_planner.llm_decision.generate_json_reply",
        lambda **kwargs: {
            "action": "ask_user",
            "destination": "제주",
            "travel_style": "휴양",
            "duration_text": "",
            "companion_type": "",
            "missing_slot": "duration_text",
            "reply": "",
        },
    )

    decision = decide_travel_planner_turn(user_message="제주로 가고 싶어")

    assert decision.action == "ask_user"
    assert decision.missing_slot == "duration_text"
    assert "제주 좋습니다. 일정은 며칠인가요?" in decision.reply
    assert CANCEL_GUIDE_REPLY in decision.reply
