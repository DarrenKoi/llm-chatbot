"""api/cube/intents.py Pydantic discriminated union 단위 테스트."""

import pytest
from pydantic import TypeAdapter, ValidationError

from api.cube.intents import (
    BlockIntent,
    ButtonIntent,
    ChoiceIntent,
    ChoiceOption,
    DatePickerIntent,
    ImageIntent,
    InputIntent,
    RawBlockIntent,
    ReplyIntent,
    TableIntent,
    TextIntent,
    is_interactive_intent,
)

# Discriminated union을 dict로부터 검증하려면 TypeAdapter 사용
_block_adapter = TypeAdapter(BlockIntent)


class TestDiscriminator:
    def test_text_kind_resolves_to_text_intent(self):
        intent = _block_adapter.validate_python({"kind": "text", "text": "hi"})
        assert isinstance(intent, TextIntent)
        assert intent.text == "hi"

    def test_table_kind_resolves_to_table_intent(self):
        intent = _block_adapter.validate_python(
            {
                "kind": "table",
                "headers": ["a", "b"],
                "rows": [["1", "2"]],
            }
        )
        assert isinstance(intent, TableIntent)

    def test_choice_kind_resolves_with_nested_options(self):
        intent = _block_adapter.validate_python(
            {
                "kind": "choice",
                "question": "Q?",
                "options": [{"label": "A", "value": "a"}],
            }
        )
        assert isinstance(intent, ChoiceIntent)
        assert intent.options[0] == ChoiceOption(label="A", value="a")
        assert intent.multi is False  # default
        assert intent.required is True  # default

    def test_image_kind_resolves(self):
        intent = _block_adapter.validate_python(
            {
                "kind": "image",
                "source_url": "http://x/y.png",
            }
        )
        assert isinstance(intent, ImageIntent)
        assert intent.alt == ""
        assert intent.link_url == ""

    def test_input_kind_resolves(self):
        intent = _block_adapter.validate_python({"kind": "input", "label": "이름"})
        assert isinstance(intent, InputIntent)
        assert intent.processid == "Sentence"  # default
        assert intent.min_length == -1
        assert intent.max_length == -1

    def test_date_kind_resolves(self):
        intent = _block_adapter.validate_python({"kind": "date", "label": "출발일"})
        assert isinstance(intent, DatePickerIntent)
        assert intent.processid == "SelectDate"

    def test_raw_block_kind_resolves(self):
        intent = _block_adapter.validate_python(
            {
                "kind": "raw_block",
                "rows": [{"bgcolor": "", "border": False, "align": "left", "width": "100%", "column": []}],
                "requestid": ["CustomProcess"],
                "bodystyle": "grid",
            }
        )
        assert isinstance(intent, RawBlockIntent)
        assert intent.bodystyle == "grid"
        assert intent.requestid == ["CustomProcess"]
        assert intent.mandatory == []  # default

    def test_button_kind_resolves(self):
        intent = _block_adapter.validate_python(
            {
                "kind": "button",
                "text": "보내기",
            }
        )
        assert isinstance(intent, ButtonIntent)
        assert intent.processid == "SendButton"  # default
        assert intent.value == ""
        assert intent.confirmmsg == ""

    def test_unknown_kind_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _block_adapter.validate_python({"kind": "unknown", "text": "x"})

    def test_missing_kind_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _block_adapter.validate_python({"text": "x"})


class TestRequiredFields:
    def test_text_intent_requires_text(self):
        with pytest.raises(ValidationError):
            TextIntent()

    def test_choice_intent_requires_question_and_options(self):
        with pytest.raises(ValidationError):
            ChoiceIntent()

    def test_image_intent_requires_source_url(self):
        with pytest.raises(ValidationError):
            ImageIntent()


class TestReplyIntent:
    def test_default_empty_blocks(self):
        reply = ReplyIntent()
        assert reply.blocks == []
        assert reply.needs_callback is False

    def test_blocks_validate_as_discriminated_union(self):
        reply = ReplyIntent.model_validate(
            {
                "blocks": [
                    {"kind": "text", "text": "hello"},
                    {"kind": "choice", "question": "Q?", "options": [{"label": "A", "value": "a"}]},
                ],
                "needs_callback": True,
            }
        )
        assert isinstance(reply.blocks[0], TextIntent)
        assert isinstance(reply.blocks[1], ChoiceIntent)
        assert reply.needs_callback is True

    def test_invalid_block_in_list_rejects_whole_reply(self):
        with pytest.raises(ValidationError):
            ReplyIntent.model_validate(
                {
                    "blocks": [{"kind": "nope"}],
                }
            )


class TestIsInteractiveIntent:
    def test_choice_is_interactive(self):
        assert is_interactive_intent(
            ChoiceIntent(question="Q", options=[ChoiceOption(label="A", value="a")])
        )

    def test_input_is_interactive(self):
        assert is_interactive_intent(InputIntent(label="이름"))

    def test_date_is_interactive(self):
        assert is_interactive_intent(DatePickerIntent(label="출발일"))

    def test_text_is_not_interactive(self):
        assert not is_interactive_intent(TextIntent(text="hi"))

    def test_table_is_not_interactive(self):
        assert not is_interactive_intent(TableIntent(headers=["h"], rows=[["v"]]))

    def test_image_is_not_interactive(self):
        assert not is_interactive_intent(ImageIntent(source_url="http://x"))

    def test_button_is_not_interactive(self):
        # 버튼 자체는 staged 입력이 아니므로 fallback 보강 대상이 아님
        assert not is_interactive_intent(ButtonIntent(text="보내기"))

    def test_raw_block_is_not_interactive(self):
        # raw_block 은 작성자가 직접 버튼을 포함시키는 escape hatch — 자동 보강하지 않음
        assert not is_interactive_intent(RawBlockIntent(rows=[]))
