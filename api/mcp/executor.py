"""MCP 도구 실행 오케스트레이션 스텁을 제공한다."""

from __future__ import annotations

from api.mcp.client import MCPClient
from api.mcp.models import MCPToolCall, MCPToolResult
from api.mcp.registry import get_server, get_tool


def execute_tool_call(tool_call: MCPToolCall) -> MCPToolResult:
    """단일 MCP 도구 호출을 실행한다."""

    tool = get_tool(tool_call.tool_id)
    client = MCPClient(get_server(tool.server_id))
    return client.execute(tool_call)


def execute_tool_calls(tool_calls: list[MCPToolCall]) -> list[MCPToolResult]:
    """여러 MCP 도구 호출을 순차 실행한다."""

    return [execute_tool_call(tool_call) for tool_call in tool_calls]
