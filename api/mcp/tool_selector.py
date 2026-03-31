"""워크플로 컨텍스트에 맞는 MCP 도구 선택 스텁을 제공한다."""

from __future__ import annotations

from api.mcp.models import MCPTool


def select_tools(*, workflow_id: str, user_message: str, tools: list[MCPTool]) -> list[MCPTool]:
    """사용할 MCP 도구 후보 목록을 반환한다."""

    del workflow_id, user_message
    return tools
