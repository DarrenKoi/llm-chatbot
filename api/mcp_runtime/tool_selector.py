"""워크플로 컨텍스트에 맞는 MCP 도구 선택 스텁을 제공한다."""

from api.mcp_runtime.models import MCPTool
from api.workflows.registry import get_workflow


def select_tools(*, workflow_id: str, user_message: str, tools: list[MCPTool]) -> list[MCPTool]:
    """사용할 MCP 도구 후보 목록을 반환한다."""

    del user_message

    workflow = get_workflow(workflow_id)
    required_tags = workflow.get("tool_tags", ())
    if not required_tags:
        return list(tools)

    required_tag_set = frozenset(required_tags)
    return [tool for tool in tools if tool.tags and not required_tag_set.isdisjoint(tool.tags)]
