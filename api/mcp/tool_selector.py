"""워크플로 컨텍스트에 맞는 MCP 도구 선택 스텁을 제공한다."""

from api.mcp.models import MCPTool
from api.workflows.registry import get_workflow


def select_tools(*, workflow_id: str, user_message: str, tools: list[MCPTool]) -> list[MCPTool]:
    """사용할 MCP 도구 후보 목록을 반환한다."""

    del user_message

    workflow = get_workflow(workflow_id)
    required_tags = workflow.get("tool_tags", ())
    if not required_tags:
        return list(tools)

    selected = [tool for tool in tools if _matches_required_tags(tool=tool, required_tags=required_tags)]
    return selected


def _matches_required_tags(*, tool: MCPTool, required_tags: tuple[str, ...]) -> bool:
    if not tool.tags:
        return False
    return any(tag in tool.tags for tag in required_tags)
