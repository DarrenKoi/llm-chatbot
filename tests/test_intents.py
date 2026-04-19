"""api/cube/intents.py Pydantic discriminated union 단위 테스트."""

import pytest
from pydantic import TypeAdapter, ValidationError

from api.cube.intents import (
    BlockIntent,
    ChoiceIntent,
    ChoiceOption,
    DatePickerIntent,
    ImageIntent,
    InputIntent,
    ReplyIntent,
    TableIntent,
    TextIntent,
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
