import json
from pathlib import Path

from tools import execute_tool
from tools.query_data import execute as query_data_execute


def test_query_data_returns_valid_json():
    result = query_data_execute("sales data")
    data = json.loads(result)
    assert data["source"] == "database"
    assert data["query"] == "sales data"
    assert len(data["results"]) > 0


def test_query_data_elasticsearch_source():
    result = query_data_execute("logs", source="elasticsearch")
    data = json.loads(result)
    assert data["source"] == "elasticsearch"


def test_execute_tool_query_data():
    result, info = execute_tool("query_data", {"query": "test"})
    assert info["success"] is True
    assert info["name"] == "query_data"
    data = json.loads(result)
    assert "results" in data


def test_execute_tool_unknown():
    result, info = execute_tool("nonexistent", {})
    assert info["success"] is False
    data = json.loads(result)
    assert "error" in data


def test_execute_tool_exception_handling():
    from unittest.mock import patch
    with patch("tools.TOOL_EXECUTORS", {"bad_tool": lambda: (_ for _ in ()).throw(ValueError("boom"))}):
        result, info = execute_tool("bad_tool", {})
        assert info["success"] is False
        assert "boom" in json.loads(result)["error"]


def test_create_chart(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "CHART_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CHART_IMAGE_BASE_URL", "http://test/charts")

    from tools.create_chart import execute as create_chart_execute
    result = create_chart_execute(
        chart_type="bar",
        title="Test Chart",
        data={"labels": ["A", "B"], "values": [10, 20]},
    )
    data = json.loads(result)
    assert "image_url" in data
    assert data["image_url"].startswith("http://test/charts/")
    assert Path(data["filepath"]).exists()


def test_create_chart_pie(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "CHART_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CHART_IMAGE_BASE_URL", "http://test/charts")

    from tools.create_chart import execute as create_chart_execute
    result = create_chart_execute(
        chart_type="pie",
        title="Pie Chart",
        data={"labels": ["X", "Y", "Z"], "values": [30, 50, 20]},
    )
    data = json.loads(result)
    assert Path(data["filepath"]).exists()
