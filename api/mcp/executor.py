"""MCP 도구 실행 오케스트레이션을 제공한다."""

from api.mcp.client import MCPClient
from api.mcp.local_tools import get_handler
from api.mcp.models import MCPToolCall, MCPToolResult
from api.mcp.registry import get_server, get_tool


def execute_tool_call(tool_call: MCPToolCall) -> MCPToolResult:
    """단일 MCP 도구 호출을 실행한다.

    로컬 핸들러가 있으면 우선 사용하고, 없으면 원격 MCPClient로 폴백한다.
    """

    handler = get_handler(tool_call.tool_id)
    if handler is not None:
        try:
            output = handler(**tool_call.arguments)
            return MCPToolResult(tool_id=tool_call.tool_id, output=output)
        except Exception as exc:
            return MCPToolResult(
                tool_id=tool_call.tool_id,
                success=False,
                error=str(exc),
            )

    tool = get_tool(tool_call.tool_id)
    client = MCPClient(get_server(tool.server_id))
    return client.execute(tool_call)


def execute_tool_calls(tool_calls: list[MCPToolCall]) -> list[MCPToolResult]:
    """여러 MCP 도구 호출을 순차 실행한다."""

    return [execute_tool_call(tool_call) for tool_call in tool_calls]
