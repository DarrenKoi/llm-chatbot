from api.mcp_runtime.models import MCPTool
from api.mcp_runtime.tool_selector import select_tools


def test_select_tools_filters_by_workflow_tool_tags(monkeypatch):
    monkeypatch.setattr(
        "api.mcp_runtime.tool_selector.get_workflow",
        lambda workflow_id: {
            "workflow_id": workflow_id,
            "tool_tags": ("translation", "language"),
        },
    )

    tools = [
        MCPTool(tool_id="translate", server_id="local", tags=("translation",)),
        MCPTool(tool_id="dictionary", server_id="local", tags=("language", "reference")),
        MCPTool(tool_id="weather", server_id="local", tags=("weather",)),
        MCPTool(tool_id="untagged", server_id="local"),
    ]

    selected = select_tools(
        workflow_id="translator",
        user_message="안녕하세요를 영어로 번역해줘",
        tools=tools,
    )

    assert [tool.tool_id for tool in selected] == ["translate", "dictionary"]


def test_select_tools_returns_all_when_workflow_has_no_tool_tags(monkeypatch):
    monkeypatch.setattr(
        "api.mcp_runtime.tool_selector.get_workflow",
        lambda workflow_id: {
            "workflow_id": workflow_id,
            "tool_tags": (),
        },
    )

    tools = [
        MCPTool(tool_id="translate", server_id="local", tags=("translation",)),
        MCPTool(tool_id="weather", server_id="local", tags=("weather",)),
    ]

    selected = select_tools(
        workflow_id="start_chat",
        user_message="오늘 일정 알려줘",
        tools=tools,
    )

    assert [tool.tool_id for tool in selected] == ["translate", "weather"]


def test_mcp_tool_tags_are_normalized_on_creation():
    tool = MCPTool(
        tool_id="translate",
        server_id="local",
        tags=(" Translation ", "LANGUAGE", "translation", ""),
    )

    assert tool.tags == ("translation", "language")
