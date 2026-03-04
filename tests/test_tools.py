import json
from pathlib import Path

from api.services.llm.tools import execute_tool


def test_execute_tool_dispatches_known_tool():
    """Verify the dispatcher routes to a registered tool and reports success."""
    result, info = execute_tool("query_data", {"query": "test"})
    assert info["success"] is True
    assert info["name"] == "query_data"
    assert info["duration_ms"] >= 0
    # result should be valid JSON regardless of content
    json.loads(result)


def test_execute_tool_unknown():
    result, info = execute_tool("nonexistent", {})
    assert info["success"] is False
    data = json.loads(result)
    assert "error" in data


def test_execute_tool_exception_handling():
    from unittest.mock import patch
    with patch("api.services.llm.tools.TOOL_EXECUTORS", {"bad_tool": lambda: (_ for _ in ()).throw(ValueError("boom"))}):
        result, info = execute_tool("bad_tool", {})
        assert info["success"] is False
        assert "boom" in json.loads(result)["error"]


def test_create_chart(tmp_path, monkeypatch):
    from api import config
    monkeypatch.setattr(config, "CHART_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CHART_IMAGE_BASE_URL", "http://test/charts")

    from api.services.llm.tools.create_chart import execute as create_chart_execute
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
    from api import config
    monkeypatch.setattr(config, "CHART_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CHART_IMAGE_BASE_URL", "http://test/charts")

    from api.services.llm.tools.create_chart import execute as create_chart_execute
    result = create_chart_execute(
        chart_type="pie",
        title="Pie Chart",
        data={"labels": ["X", "Y", "Z"], "values": [30, 50, 20]},
    )
    data = json.loads(result)
    assert Path(data["filepath"]).exists()
