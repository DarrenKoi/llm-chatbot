"""api/cube/rich_blocks.py 단위 테스트."""

from api.cube import rich_blocks
from api.cube.rich_blocks import (
    LANG_COUNT,
    SYSTEM_REQUEST_IDS,
    Block,
    add_button,
    add_choice,
    add_container,
    add_datepicker,
    add_image,
    add_input,
    add_select,
    add_table,
    add_text,
    make_hypertext_cell,
    make_label_cell,
    make_radio_cell,
)


class TestLang5:
    def test_string_expands_to_5_slots_with_korean_first(self):
        result = rich_blocks._lang5("안녕")
        assert result == ["안녕", "", "", "", ""]
        assert len(result) == LANG_COUNT

    def test_short_list_padded_to_5(self):
        result = rich_blocks._lang5(["안녕", "Hello"])
        assert result == ["안녕", "Hello", "", "", ""]
        assert len(result) == LANG_COUNT

    def test_long_list_truncated_to_5(self):
        result = rich_blocks._lang5(["a", "b", "c", "d", "e", "f", "g"])
        assert len(result) == LANG_COUNT
        assert result == ["a", "b", "c", "d", "e"]


class TestCellMakers:
    def test_make_label_cell(self):
        cell = make_label_cell("안녕하세요", align="center")
        assert cell["type"] == "label"
        assert cell["align"] == "center"
        assert cell["control"]["text"] == ["안녕하세요", "", "", "", ""]
        assert cell["control"]["color"] == "#000000"

    def test_make_hypertext_cell(self):
        cell = make_hypertext_cell("문서", "https://example.com/doc")
        assert cell["type"] == "hypertext"
        assert cell["control"]["text"] == ["문서", "", "", "", ""]
        assert cell["control"]["linkurl"] == "https://example.com/doc"
        assert cell["control"]["opengraph"] is True

    def test_make_radio_cell(self):
        cell = make_radio_cell("국내", "domestic", processid="TripType", checked=True)
        assert cell["type"] == "radio"
        assert cell["control"]["processid"] == "TripType"
        assert cell["control"]["value"] == "domestic"
        assert cell["control"]["checked"] is True


class TestAddComponents:
    def test_add_text_produces_label_row(self):
        block = add_text("안녕하세요")
        assert isinstance(block, Block)
        assert block.requestid == []
        assert block.mandatory == []
        assert block.bodystyle == "none"
        assert block.rows[0]["column"][0]["type"] == "label"

    def test_add_image_basic(self):
        block = add_image("http://x/y.png", alt="차트")
        cell = block.rows[0]["column"][0]
        assert cell["type"] == "image"
        assert cell["control"]["sourceurl"] == "http://x/y.png"
        assert cell["control"]["text"] == ["차트", "", "", "", ""]
        assert cell["control"]["location"] is True
        assert cell["control"]["inner"] is True
        assert cell["control"]["displaytype"] == "resize"
        assert block.requestid == []

    def test_add_button_registers_processid_in_requestid(self):
        block = add_button("저장", processid="SaveBtn")
        assert block.requestid == ["SaveBtn"]
        cell = block.rows[0]["column"][0]
        assert cell["type"] == "button"
        assert cell["control"]["processid"] == "SaveBtn"

    def test_add_choice_radio_when_multi_false(self):
        block = add_choice(
            "여행 유형",
            [("국내", "domestic"), ("해외", "overseas")],
            processid="TripType",
        )
        assert block.rows[0]["column"][0]["type"] == "label"
        for option_row in block.rows[1:]:
            assert option_row["column"][0]["type"] == "radio"
            assert option_row["column"][0]["control"]["processid"] == "TripType"
        assert block.requestid == ["TripType"]
        assert block.mandatory == []

    def test_add_choice_checkbox_when_multi_true(self):
        block = add_choice(
            "관심사",
            [("Python", "py"), ("Go", "go")],
            multi=True,
        )
        for option_row in block.rows[1:]:
            assert option_row["column"][0]["type"] == "checkbox"

    def test_add_choice_required_adds_mandatory(self):
        block = add_choice(
            "필수 선택",
            [("A", "a")],
            processid="MustPick",
            required=True,
            alertmsg="선택해 주세요",
        )
        assert block.mandatory == [
            {"processid": "MustPick", "alertmsg": ["선택해 주세요", "", "", "", ""]},
        ]

    def test_add_choice_required_uses_question_as_default_alertmsg(self):
        block = add_choice("질문", [("A", "a")], required=True)
        assert block.mandatory[0]["alertmsg"] == ["질문", "", "", "", ""]

    def test_add_choice_default_value_marks_checked(self):
        block = add_choice("Q", [("A", "a"), ("B", "b")], default_value="b")
        assert block.rows[1]["column"][0]["control"]["checked"] is False
        assert block.rows[2]["column"][0]["control"]["checked"] is True

    def test_add_input_required_adds_mandatory_and_requestid(self):
        block = add_input("이름", processid="UserName", required=True)
        assert block.requestid == ["UserName"]
        assert block.mandatory == [
            {"processid": "UserName", "alertmsg": ["이름", "", "", "", ""]},
        ]
        assert block.rows[0]["column"][0]["type"] == "inputtext"

    def test_add_select_default_value_marks_selected(self):
        block = add_select("유형", [("A", "a"), ("B", "b")], default_value="a")
        items = block.rows[0]["column"][0]["control"]["item"]
        assert items[0]["selected"] is True
        assert items[1]["selected"] is False

    def test_add_datepicker_required(self):
        block = add_datepicker("출발일", required=True)
        assert block.requestid == ["SelectDate"]
        assert block.mandatory[0]["processid"] == "SelectDate"


class TestAddTable:
    def test_add_table_uses_grid_bodystyle(self):
        block = add_table(["a", "b"], [["1", "2"]])
        assert block.bodystyle == "grid"

    def test_add_table_pads_short_rows_with_empty(self):
        block = add_table(["A", "B", "C"], [["1"], ["x", "y", "z", "w"]])
        assert len(block.rows) == 3
        for row in block.rows:
            assert len(row["column"]) == 4

    def test_add_table_empty_returns_empty_grid(self):
        block = add_table([], [])
        assert block.bodystyle == "grid"
        assert block.rows == []

    def test_add_table_accepts_hypertext_cells(self):
        block = add_table(
            ["이름", "링크"],
            [["문서", make_hypertext_cell("열기", "https://example.com")]],
        )
        link_cell = block.rows[1]["column"][1]
        assert link_cell["type"] == "hypertext"
        assert link_cell["width"] == "50%"
        assert link_cell["border"] is True
        assert link_cell["control"]["linkurl"] == "https://example.com"


class TestAddContainer:
    def test_appends_system_request_ids(self):
        item = add_container(add_button("OK", processid="Confirm"))
        assert item["process"]["requestid"][0] == "Confirm"
        for sys_id in SYSTEM_REQUEST_IDS:
            assert sys_id in item["process"]["requestid"]

    def test_deduplicates_request_ids(self):
        item = add_container(add_button("A", processid="Same"), add_button("B", processid="Same"))
        assert item["process"]["requestid"].count("Same") == 1

    def test_accumulates_mandatory(self):
        item = add_container(
            add_input("L1", processid="P1", required=True), add_input("L2", processid="P2", required=True)
        )
        processids = [m["processid"] for m in item["process"]["mandatory"]]
        assert processids == ["P1", "P2"]

    def test_callback_address_sets_callbacktype_url(self):
        item = add_container(add_text("hi"), callback_address="http://srv/cb")
        assert item["process"]["callbacktype"] == "url"
        assert item["process"]["callbackaddress"] == "http://srv/cb"

    def test_no_callback_address_clears_callbacktype(self):
        item = add_container(add_text("hi"))
        assert item["process"]["callbacktype"] == ""
        assert item["process"]["callbackaddress"] == ""

    def test_grid_bodystyle_inherited_from_table(self):
        item = add_container(add_text("title"), add_table(["h"], [["v"]]))
        assert item["body"]["bodystyle"] == "grid"

    def test_session_id_and_sequence_propagate(self):
        item = add_container(add_text("hi"), session_id="S1", sequence="3")
        assert item["process"]["session"] == {"sessionid": "S1", "sequence": "3"}

    def test_summary_lang5_expansion(self):
        item = add_container(add_text("hi"), summary="요약")
        assert item["process"]["summary"] == ["요약", "", "", "", ""]


def test_previous_block_function_names_are_removed():
    for name in (
        "text_block",
        "button_block",
        "choice_block",
        "input_block",
        "textarea_block",
        "select_block",
        "datepicker_block",
        "datetimepicker_block",
        "image_block",
        "hypertext_block",
        "table_block",
        "compose_content_item",
    ):
        assert not hasattr(rich_blocks, name)
