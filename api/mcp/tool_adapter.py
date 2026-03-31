"""MCP 도구 스키마를 내부 호출 형식으로 바꾸는 스텁이다."""

from __future__ import annotations

from typing import Any

from api.mcp.models import MCPTool, MCPToolCall


def adapt_tool_call(tool: MCPTool, arguments: dict[str, Any]) -> MCPToolCall:
    """도구 메타데이터와 입력값을 호출 객체로 변환한다."""

    return MCPToolCall(tool_id=tool.tool_id, arguments=arguments)
