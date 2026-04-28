"""MCP 서버와 도구 레지스트리 스텁을 제공한다."""

from __future__ import annotations

from api.mcp_client.errors import MCPRegistryError
from api.mcp_client.models import MCPServerConfig, MCPTool

_SERVERS: dict[str, MCPServerConfig] = {}
_TOOLS: dict[str, MCPTool] = {}


def register_server(config: MCPServerConfig) -> MCPServerConfig:
    """MCP 서버 구성을 등록한다."""

    _SERVERS[config.server_id] = config
    return config


def register_tool(tool: MCPTool) -> MCPTool:
    """MCP 도구 메타데이터를 등록한다."""

    _TOOLS[tool.tool_id] = tool
    return tool


def get_server(server_id: str) -> MCPServerConfig:
    """등록된 MCP 서버 구성을 반환한다."""

    try:
        return _SERVERS[server_id]
    except KeyError as exc:
        raise MCPRegistryError(f"등록되지 않은 MCP 서버입니다: {server_id}") from exc


def get_tool(tool_id: str) -> MCPTool:
    """등록된 MCP 도구 메타데이터를 반환한다."""

    try:
        return _TOOLS[tool_id]
    except KeyError as exc:
        raise MCPRegistryError(f"등록되지 않은 MCP 도구입니다: {tool_id}") from exc


def list_tools(server_id: str | None = None) -> list[MCPTool]:
    """조건에 맞는 MCP 도구 목록을 반환한다."""

    if server_id is None:
        return list(_TOOLS.values())
    return [tool for tool in _TOOLS.values() if tool.server_id == server_id]
