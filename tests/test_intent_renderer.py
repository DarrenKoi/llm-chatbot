"""api/cube/intent_renderer.py 단위 테스트."""

import pytest

from api.cube import rich_blocks
from api.cube.intent_renderer import (
    intent_to_block,
    intents_to_blocks,
    intents_to_content_item,
)
from api.cube.intents import (
    ChoiceIntent,
    ChoiceOption,
    DatePickerIntent,
    ImageIntent,
    InputIntent,
    RawBlockIntent,
    TableIntent,
    TextIntent,
)


class TestIntentToBlock:
    def test_text_intent(self):
        block = intent_to_block(TextIntent(text="안녕"))
        assert isinstance(block, rich_blocks.Block)
        col = block.rows[0]["column"][0]
        assert col["type"] == "label"
        assert col["control"]["text"] == ["안녕", "", "", "", ""]

    def test_table_intent_uses_grid(self):
        block = intent_to_block(TableIntent(headers=["h"], rows=[["v"]]))
        assert block.bodystyle == "grid"

    def test_image_intent_passes_link_url(self):
        block = intent_to_block(
            ImageIntent(
                source_url="http://x/y.png",
                alt="alt",
                link_url="http://link",
            )
        )
        col = block.rows[0]["column"][0]
        assert col["type"] == "image"
        assert col["control"]["sourceurl"] == "http://x/y.png"
        assert col["control"]["linkurl"] == "http://link"

    def test_choice_intent_radio_with_processid_grouping(self):
        block = intent_to_block(
            ChoiceIntent(
                question="여행",
                options=[ChoiceOption(label="국내", value="d"), ChoiceOption(label="해외", value="o")],
                processid="TripType",
            )
        )
        # 같은 processid를 두 옵션이 공유 → 라디오 그룹
        radio_rows = [row for row in block.rows if row["column"][0]["type"] == "radio"]
        assert len(radio_rows) == 2
        for row in radio_rows:
            assert row["column"][0]["control"]["processid"] == "TripType"
        assert block.requestid == ["TripType"]

    def test_choice_intent_multi_true_uses_checkbox(self):
        block = intent_to_block(
            ChoiceIntent(
                question="언어",
                options=[ChoiceOption(label="Py", value="py")],
                multi=True,
            )
        )
        checkbox_rows = [row for row in block.rows if row["column"][0]["type"] == "checkbox"]
        assert len(checkbox_rows) == 1

    def test_choice_intent_required_default_creates_mandatory(self):
        block = intent_to_block(
            ChoiceIntent(
                question="필수",
                options=[ChoiceOption(label="A", value="a")],
                processid="P",
            )
        )
        # required default = True → mandatory 등록
        assert block.mandatory == [
            {"processid": "P", "alertmsg": ["필수", "", "", "", ""]},
        ]

    def test_input_intent_propagates_lengths(self):
        block = intent_to_block(
            InputIntent(
                label="코드",
                min_length=2,
                max_length=10,
                required=False,
            )
        )
        col = block.rows[0]["column"][0]
        assert col["type"] == "inputtext"
        assert col["control"]["minlength"] == 2
        assert col["control"]["maxlength"] == 10
        assert block.mandatory == []

    def test_date_intent(self):
        block = intent_to_block(DatePickerIntent(label="출발일", default="2026/04/20"))
        col = block.rows[0]["column"][0]
        assert col["type"] == "datepicker"
        assert col["control"]["value"] == "2026/04/20"

    def test_raw_block_intent_passes_rows_through_unchanged(self):
        custom_rows = [
            {
                "bgcolor": "",
                "border": False,
                "align": "left",
                "width": "100%",
                "column": [
                    {
                        "bgcolor": "",
                        "border": False,
                        "align": "left",
                        "valign": "middle",
                        "width": "100%",
                        "type": "label",
                        "control": {"active": True, "text": ["raw", "", "", "", ""], "color": "#000"},
                    }
                ],
            }
        ]
        block = intent_to_block(
            RawBlockIntent(
                rows=custom_rows,
                requestid=["CustomProcess"],
                bodystyle="grid",
            )
        )
        assert isinstance(block, rich_blocks.Block)
        assert block.rows == custom_rows
        assert block.requestid == ["CustomProcess"]
        assert block.bodystyle == "grid"

    def test_raw_block_intent_grid_bodystyle_propagates_through_container(self):
        custom_rows = [{"column": [], "bgcolor": "", "border": False, "align": "left", "width": "100%"}]
        item = intents_to_content_item(
            [
                TextIntent(text="title"),
                RawBlockIntent(rows=custom_rows, bodystyle="grid"),
            ]
        )
        assert item["body"]["bodystyle"] == "grid"


class TestIntentsToBlocks:
    def test_preserves_order(self):
        intents = [
            TextIntent(text="첫째"),
            TextIntent(text="둘째"),
            TextIntent(text="셋째"),
        ]
        blocks = intents_to_blocks(intents)
        texts = [b.rows[0]["column"][0]["control"]["text"][0] for b in blocks]
        assert texts == ["첫째", "둘째", "셋째"]

    def test_empty_list(self):
        assert intents_to_blocks([]) == []


class TestIntentsToContentItem:
    def test_returns_add_container_dict_shape(self):
        item = intents_to_content_item(
            [
                TextIntent(text="hi"),
                ChoiceIntent(
                    question="Q",
                    options=[ChoiceOption(label="A", value="a")],
                    processid="P",
                ),
            ],
        )
        assert "header" in item
        assert "body" in item
        assert "process" in item
        assert item["body"]["bodystyle"] == "none"
        # 같은 매크로가 시스템 ID를 추가하므로 P + 5개 시스템 ID가 들어 있어야 함
        assert "P" in item["process"]["requestid"]
        for sys_id in rich_blocks.SYSTEM_REQUEST_IDS:
            assert sys_id in item["process"]["requestid"]

    def test_callback_address_propagates(self):
        item = intents_to_content_item(
            [TextIntent(text="hi")],
            callback_address="http://srv/cb",
            session_id="S1",
            sequence="2",
        )
        assert item["process"]["callbackaddress"] == "http://srv/cb"
        assert item["process"]["callbacktype"] == "url"
        assert item["process"]["session"] == {"sessionid": "S1", "sequence": "2"}

    def test_table_intent_propagates_grid_bodystyle(self):
        item = intents_to_content_item(
            [TextIntent(text="title"), TableIntent(headers=["h"], rows=[["v"]])],
        )
        assert item["body"]["bodystyle"] == "grid"


def test_intent_to_block_rejects_unknown_type():
    class FakeIntent:
        pass

    with pytest.raises(TypeError, match="Unknown intent kind"):
        intent_to_block(FakeIntent())  # type: ignore[arg-type]
