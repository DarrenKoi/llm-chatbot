"""devtools LangGraph 워크플로 예제의 회귀 동작을 검증한다."""

from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from devtools.workflows.richinotification_test import build_lg_graph as build_rich_graph
from devtools.workflows.richinotification_test.block_builder import build_text_table_blocks, compose_content_items
from devtools.workflows.travel_planner_example import build_lg_graph as build_travel_graph


def _compile_graph(builder):
    return builder().compile(checkpointer=MemorySaver())


def _make_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def test_travel_planner_example_completes_after_collecting_missing_info():
    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-complete")

    graph.invoke(
        {"user_message": "오사카 여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    result = graph.invoke(Command(resume="2박 3일"), config)

    assert "오사카 2박 3일 여행" in result["messages"][-1].content


def test_travel_planner_example_stop_message_completes_cleanly():
    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-stop")

    graph.invoke(
        {"user_message": "여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    result = graph.invoke(Command(resume="bye"), config)

    assert result["messages"][-1].content == "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."


@patch("devtools.workflows.travel_planner_example.lg_graph.recommend_destinations", return_value=["제주", "삿포로"])
def test_travel_planner_example_interrupts_with_recommendation(mock_recommend):
    del mock_recommend

    graph = _compile_graph(build_travel_graph)
    config = _make_config("travel-recommend")

    graph.invoke(
        {"user_message": "휴양 여행 계획 짜줘", "user_id": "dev-user", "workflow_id": "travel_planner_example"},
        config,
    )

    state = graph.get_state(config)
    assert state.tasks
    assert "제주, 삿포로" in state.tasks[0].interrupts[0].value["reply"]


def test_richinotification_test_composes_text_and_datatable_content():
    blocks, headers, rows = build_text_table_blocks(
        "GPU 비용 비교\n| 항목 | 값 |\n| --- | --- |\n| A100 | 3 |\n| H100 | 1 |"
    )

    content_items = compose_content_items(blocks)
    content = content_items[0]
    table_header_row = next(row for row in content["body"]["row"] if row["column"][0]["control"]["text"][0] == "항목")

    assert headers == ["항목", "값"]
    assert rows == [["A100", "3"], ["H100", "1"]]
    assert content["body"]["bodystyle"] == "grid"
    assert table_header_row["column"][0]["type"] == "label"
    assert table_header_row["column"][0]["border"] is True
    assert content["process"]["session"]["sessionid"] == "devtools-richnotification-test"


def test_richinotification_test_graph_returns_preview_payload_without_token():
    graph = _compile_graph(build_rich_graph)
    config = _make_config("rich-preview")

    result = graph.invoke(
        {
            "user_message": "서버별 처리량\n| 서버 | TPS |\n| --- | --- |\n| api-1 | 120 |",
            "user_id": "dev-user",
            "workflow_id": "richinotification_test",
        },
        config,
    )

    assert "This is done via devtools." in result["messages"][-1].content
    assert result["delivery_mode"] == "preview"
    assert result["payload_preview"]["richnotification"]["header"]["token"] == "<redacted>"
    assert result["payload_preview"]["richnotification"]["header"]["to"]["channelid"] == [""]
    assert result["table_headers"] == ["서버", "TPS"]


def test_richinotification_test_graph_sends_when_target_is_provided(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_send_richnotification_blocks(*blocks, **kwargs):
        captured["block_count"] = len(blocks)
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "devtools.workflows.richinotification_test.lg_graph.send_richnotification_blocks",
        _fake_send_richnotification_blocks,
    )
    graph = _compile_graph(build_rich_graph)
    config = _make_config("rich-send")

    result = graph.invoke(
        {
            "user_message": "send to=X905552 channel=C123\n| 항목 | 값 |\n| --- | --- |\n| 완료 | yes |",
            "user_id": "dev-user",
            "workflow_id": "richinotification_test",
        },
        config,
    )

    assert result["delivery_mode"] == "sent"
    assert captured["block_count"] >= 3
    assert captured["user_id"] == "X905552"
    assert captured["channel_id"] == "C123"
    assert captured["callback_address"] == ""


def test_richinotification_test_graph_does_not_send_without_real_target():
    graph = _compile_graph(build_rich_graph)
    config = _make_config("rich-missing-target")

    result = graph.invoke(
        {
            "user_message": "send\n| 항목 | 값 |\n| --- | --- |\n| 완료 | yes |",
            "user_id": "dev-user",
            "workflow_id": "richinotification_test",
        },
        config,
    )

    assert result["delivery_mode"] == "preview_missing_target"
    assert "no real Cube target" in result["messages"][-1].content
