"""api.cube.chunker 모듈 단위 테스트."""

import pytest

from api.cube.chunker import DeliveryItem, plan_delivery


@pytest.fixture()
def _enable_rich_routing(monkeypatch):
    """CUBE_RICH_ROUTING_ENABLED를 켜는 픽스처."""
    from api import config

    monkeypatch.setattr(config, "CUBE_RICH_ROUTING_ENABLED", True)


# ---------------------------------------------------------------------------
# 기본 동작 (rich routing OFF — 기본값)
# ---------------------------------------------------------------------------


def test_short_text_returns_single_multi():
    result = plan_delivery("안녕하세요", max_lines=40)
    assert len(result) == 1
    assert result[0] == DeliveryItem(method="multi", content="안녕하세요")


def test_empty_text_returns_single_empty():
    result = plan_delivery("", max_lines=40)
    assert len(result) == 1
    assert result[0].method == "multi"


def test_whitespace_only_returns_single_empty():
    result = plan_delivery("   \n\n  ", max_lines=40)
    assert len(result) == 1
    assert result[0].method == "multi"


# ---------------------------------------------------------------------------
# rich routing OFF → 코드/표도 multimessage로 청킹
# ---------------------------------------------------------------------------


def test_code_block_goes_to_multi_when_rich_disabled():
    text = "```python\nprint('hello')\n```"
    result = plan_delivery(text, max_lines=40)
    assert all(item.method == "multi" for item in result)
    assert "print('hello')" in result[0].content


def test_table_goes_to_multi_when_rich_disabled():
    text = "| 이름 | 값 |\n|---|---|\n| A | 1 |"
    result = plan_delivery(text, max_lines=40)
    assert all(item.method == "multi" for item in result)


# ---------------------------------------------------------------------------
# rich routing ON → 코드/표는 richnotification
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_enable_rich_routing")
def test_code_block_routed_to_rich():
    text = "```python\nprint('hello')\n```"
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 1
    assert result[0].method == "rich"
    assert "print('hello')" in result[0].content


@pytest.mark.usefixtures("_enable_rich_routing")
def test_text_then_code_block():
    text = "설명입니다.\n\n```python\nprint('hello')\n```"
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 2
    assert result[0].method == "multi"
    assert result[1].method == "rich"


@pytest.mark.usefixtures("_enable_rich_routing")
def test_code_block_then_text():
    text = "```\ncode\n```\n\n후속 설명입니다."
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 2
    assert result[0].method == "rich"
    assert result[1].method == "multi"


@pytest.mark.usefixtures("_enable_rich_routing")
def test_code_block_with_language_tag():
    text = "```javascript\nconsole.log('hi')\n```"
    result = plan_delivery(text, max_lines=40)
    assert result[0].method == "rich"
    assert "javascript" in result[0].content


@pytest.mark.usefixtures("_enable_rich_routing")
def test_unclosed_code_fence_treated_as_code():
    """닫히지 않은 코드 펜스도 코드 블록으로 처리."""
    text = "```python\nline1\nline2"
    result = plan_delivery(text, max_lines=40)
    assert result[0].method == "rich"


@pytest.mark.usefixtures("_enable_rich_routing")
def test_table_routed_to_rich():
    text = "| 이름 | 값 |\n|---|---|\n| A | 1 |\n| B | 2 |"
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 1
    assert result[0].method == "rich"


@pytest.mark.usefixtures("_enable_rich_routing")
def test_text_then_table():
    text = "결과는 다음과 같습니다.\n\n| 이름 | 값 |\n|---|---|\n| A | 1 |"
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 2
    assert result[0].method == "multi"
    assert result[1].method == "rich"


@pytest.mark.usefixtures("_enable_rich_routing")
def test_mixed_text_code_table_with_rich():
    text = (
        "소개 텍스트입니다.\n\n"
        "```python\ndef hello():\n    pass\n```\n\n"
        "중간 설명.\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "마무리 텍스트."
    )
    result = plan_delivery(text, max_lines=40)
    methods = [item.method for item in result]
    assert "multi" in methods
    assert "rich" in methods


@pytest.mark.usefixtures("_enable_rich_routing")
def test_multiple_code_blocks_with_rich():
    text = "첫 코드:\n\n```\ncode1\n```\n\n두 번째 코드:\n\n```\ncode2\n```"
    result = plan_delivery(text, max_lines=40)
    rich_items = [item for item in result if item.method == "rich"]
    assert len(rich_items) == 2


# ---------------------------------------------------------------------------
# 텍스트 청킹 (40줄 한도)
# ---------------------------------------------------------------------------


def test_text_within_limit_no_chunking():
    lines = ["줄 " + str(i) for i in range(30)]
    text = "\n".join(lines)
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 1
    assert result[0].method == "multi"


def test_long_text_chunked_at_paragraph_boundary():
    para1 = "\n".join([f"문단1 줄{i}" for i in range(25)])
    para2 = "\n".join([f"문단2 줄{i}" for i in range(25)])
    text = para1 + "\n\n" + para2

    result = plan_delivery(text, max_lines=40)
    assert len(result) == 2
    assert all(item.method == "multi" for item in result)
    for item in result:
        assert item.content.count("\n") + 1 <= 40


def test_very_long_single_paragraph_falls_back_to_line_split():
    lines = [f"줄{i}" for i in range(60)]
    text = "\n".join(lines)
    result = plan_delivery(text, max_lines=40)
    assert len(result) >= 2
    for item in result:
        assert item.content.count("\n") + 1 <= 40


def test_header_triggers_new_chunk():
    """마크다운 헤더에서 새 청크 시작."""
    para1 = "\n".join([f"내용{i}" for i in range(35)])
    text = para1 + "\n\n## 새 섹션\n\n" + "\n".join([f"내용{i}" for i in range(10)])
    result = plan_delivery(text, max_lines=40)
    assert len(result) >= 2


# ---------------------------------------------------------------------------
# 한국어 텍스트
# ---------------------------------------------------------------------------


def test_korean_paragraph_split():
    para1 = "\n".join([f"한국어 문장 {i}번입니다." for i in range(25)])
    para2 = "\n".join([f"두번째 문단 {i}번입니다." for i in range(25)])
    text = para1 + "\n\n" + para2
    result = plan_delivery(text, max_lines=40)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# max_lines 파라미터 오버라이드
# ---------------------------------------------------------------------------


def test_custom_max_lines():
    lines = [f"줄{i}" for i in range(20)]
    text = "\n".join(lines)
    result = plan_delivery(text, max_lines=10)
    assert len(result) >= 2


# ---------------------------------------------------------------------------
# 인접 병합
# ---------------------------------------------------------------------------


def test_adjacent_short_multi_items_merged():
    """rich routing OFF일 때 인접한 짧은 multi 항목은 병합."""
    text = "짧은 텍스트1.\n\n```\ncode\n```\n\n짧은 텍스트2."
    result = plan_delivery(text, max_lines=40)
    # rich routing off → 전부 multi → 40줄 이내면 하나로 병합
    assert all(item.method == "multi" for item in result)
