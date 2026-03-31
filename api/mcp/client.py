"""MCP 서버와 통신하는 클라이언트 스텁을 제공한다."""

from __future__ import annotations

from api.mcp.models import MCPServerConfig, MCPToolCall, MCPToolResult


class MCPClient:
    """MCP 서버 단위 호출을 감싸는 얇은 클라이언트 스텁이다."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config

    def execute(self, tool_call: MCPToolCall) -> MCPToolResult:
        """MCP 도구 호출을 실행한다."""

        return MCPToolResult(tool_id=tool_call.tool_id, output={"arguments": tool_call.arguments})
