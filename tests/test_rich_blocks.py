"""api/cube/rich_blocks.py 단위 테스트."""

from api.cube import rich_blocks
from api.cube.rich_blocks import (
    LANG_COUNT,
    SYSTEM_REQUEST_IDS,
    Block,
    button_block,
    choice_block,
    compose_content_item,
    datepicker_block,
    image_block,
    input_block,
    select_block,
    table_block,
    text_block,
)

# ---------------------------------------------------------------------------
# 5개 언어 배열 규약
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 텍스트·이미지 등 비-인터랙션 블록
# ---------------------------------------------------------------------------


class TestTextBlock:
    def test_text_block_produces_label_column(self):
        block = text_block("안녕하세요")
        assert isinstance(block, Block)
        assert block.requestid == []
        assert block.mandatory == []
        assert block.bodystyle == "none"
        assert len(block.rows) == 1
        col = block.rows[0]["column"][0]
        assert col["type"] == "label"
        assert col["control"]["text"] == ["안녕하세요", "", "", "", ""]
        assert col["control"]["color"] == "#000000"

    def test_text_block_respects_align(self):
        block = text_block("center", align="center")
        assert block.rows[0]["align"] == "center"
        assert block.rows[0]["column"][0]["align"] == "center"


class TestImageBlock:
    def test_image_block_basic(self):
        block = image_block("http://x/y.png", alt="차트")
        col = block.rows[0]["column"][0]
        assert col["type"] == "image"
        assert col["control"]["sourceurl"] == "http://x/y.png"
        assert col["control"]["text"] == ["차트", "", "", "", ""]
        assert col["control"]["location"] is True
        assert col["control"]["inner"] is True
        assert col["control"]["displaytype"] == "resize"
        assert block.requestid == []


# ---------------------------------------------------------------------------
# 인터랙션 블록 (requestid, mandatory)
# ---------------------------------------------------------------------------


class TestButtonBlock:
    def test_button_block_registers_processid_in_requestid(self):
        block = button_block("저장", processid="SaveBtn")
        assert block.requestid == ["SaveBtn"]
        col = block.rows[0]["column"][0]
        assert col["type"] == "button"
        assert col["control"]["processid"] == "SaveBtn"


class TestChoiceBlock:
    def test_choice_block_radio_when_multi_false(self):
        block = choice_block(
            "여행 유형",
            [("국내", "domestic"), ("해외", "overseas")],
            processid="TripType",
        )
        # 첫 행은 질문 라벨
        assert block.rows[0]["column"][0]["type"] == "label"
        # 이후 행들은 radio (multi=False)
        for option_row in block.rows[1:]:
            assert option_row["column"][0]["type"] == "radio"
            assert option_row["column"][0]["control"]["processid"] == "TripType"
        assert block.requestid == ["TripType"]
        assert block.mandatory == []  # required=False default

    def test_choice_block_checkbox_when_multi_true(self):
        block = choice_block(
            "관심사",
            [("Python", "py"), ("Go", "go")],
            multi=True,
        )
        for option_row in block.rows[1:]:
            assert option_row["column"][0]["type"] == "checkbox"

    def test_choice_block_required_adds_mandatory(self):
        block = choice_block(
            "필수 선택",
            [("A", "a")],
            processid="MustPick",
            required=True,
            alertmsg="선택해 주세요",
        )
        assert block.mandatory == [
            {"processid": "MustPick", "alertmsg": ["선택해 주세요", "", "", "", ""]},
        ]

    def test_choice_block_required_uses_question_as_default_alertmsg(self):
        block = choice_block("질문", [("A", "a")], required=True)
        assert block.mandatory[0]["alertmsg"] == ["질문", "", "", "", ""]

    def test_choice_block_default_value_marks_checked(self):
        block = choice_block(
            "Q",
            [("A", "a"), ("B", "b")],
            default_value="b",
        )
        # 첫 행은 질문, 두 번째 행이 "A", 세 번째가 "B"
        assert block.rows[1]["column"][0]["control"]["checked"] is False
        assert block.rows[2]["column"][0]["control"]["checked"] is True


class TestInputBlock:
    def test_input_block_required_adds_mandatory_and_requestid(self):
        block = input_block("이름", processid="UserName", required=True)
        assert block.requestid == ["UserName"]
        assert block.mandatory == [
            {"processid": "UserName", "alertmsg": ["이름", "", "", "", ""]},
        ]
        col = block.rows[0]["column"][0]
        assert col["type"] == "inputtext"

    def test_input_block_min_max_length(self):
        block = input_block("코드", min_length=2, max_length=10)
        col = block.rows[0]["column"][0]
        assert col["control"]["minlength"] == 2
        assert col["control"]["maxlength"] == 10


class TestSelectBlock:
    def test_select_block_default_value_marks_selected(self):
        block = select_block(
            "유형",
            [("A", "a"), ("B", "b")],
            default_value="a",
        )
        items = block.rows[0]["column"][0]["control"]["item"]
        assert items[0]["selected"] is True
        assert items[1]["selected"] is False


class TestDatepickerBlock:
    def test_datepicker_block_required(self):
        block = datepicker_block("출발일", required=True)
        assert block.requestid == ["SelectDate"]
        assert block.mandatory[0]["processid"] == "SelectDate"


class TestTableBlock:
    def test_table_block_uses_grid_bodystyle(self):
        block = table_block(["a", "b"], [["1", "2"]])
        assert block.bodystyle == "grid"

    def test_table_block_pads_short_rows_with_empty(self):
        block = table_block(["A", "B", "C"], [["1"], ["x", "y", "z", "w"]])
        # 헤더 1행 + 본문 2행 = 3행. 칸 수는 max(3, 4) = 4
        assert len(block.rows) == 3
        for row in block.rows:
            assert len(row["column"]) == 4

    def test_table_block_empty_returns_empty_grid(self):
        block = table_block([], [])
        assert block.bodystyle == "grid"
        assert block.rows == []


# ---------------------------------------------------------------------------
# compose_content_item
# ---------------------------------------------------------------------------


class TestComposeContentItem:
    def test_appends_system_request_ids(self):
        block = button_block("OK", processid="Confirm")
        item = compose_content_item(block)
        # Confirm + 시스템 5종 = 6
        assert item["process"]["requestid"][0] == "Confirm"
        for sys_id in SYSTEM_REQUEST_IDS:
            assert sys_id in item["process"]["requestid"]

    def test_deduplicates_request_ids(self):
        b1 = button_block("A", processid="Same")
        b2 = button_block("B", processid="Same")
        item = compose_content_item(b1, b2)
        assert item["process"]["requestid"].count("Same") == 1

    def test_accumulates_mandatory(self):
        b1 = input_block("L1", processid="P1", required=True)
        b2 = input_block("L2", processid="P2", required=True)
        item = compose_content_item(b1, b2)
        processids = [m["processid"] for m in item["process"]["mandatory"]]
        assert processids == ["P1", "P2"]

    def test_callback_address_sets_callbacktype_url(self):
        item = compose_content_item(text_block("hi"), callback_address="http://srv/cb")
        assert item["process"]["callbacktype"] == "url"
        assert item["process"]["callbackaddress"] == "http://srv/cb"

    def test_no_callback_address_clears_callbacktype(self):
        item = compose_content_item(text_block("hi"))
        assert item["process"]["callbacktype"] == ""
        assert item["process"]["callbackaddress"] == ""

    def test_grid_bodystyle_inherited_from_table(self):
        item = compose_content_item(text_block("title"), table_block(["h"], [["v"]]))
        assert item["body"]["bodystyle"] == "grid"

    def test_session_id_and_sequence_propagate(self):
        item = compose_content_item(
            text_block("hi"),
            session_id="S1",
            sequence="3",
        )
        assert item["process"]["session"] == {"sessionid": "S1", "sequence": "3"}

    def test_summary_lang5_expansion(self):
        item = compose_content_item(text_block("hi"), summary="요약")
        assert item["process"]["summary"] == ["요약", "", "", "", ""]
