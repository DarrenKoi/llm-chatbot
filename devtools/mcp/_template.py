"""__WORKFLOW_ID__ 워크플로용 dev MCP 스텁.

필요한 MCP 서버/도구 등록 로직을 이 파일에 추가한다.
promotion 시 같은 이름의 모듈이 `api/mcp/`로 함께 이동한다.
"""


def register_tools() -> None:
    """__WORKFLOW_ID__ 워크플로용 MCP 도구를 등록한다."""

    # 예시:
    # from api.mcp.local_tools import register_handler
    # from api.mcp.models import MCPServerConfig, MCPTool
    # from api.mcp.registry import register_server, register_tool
    #
    # server = MCPServerConfig(
    #     server_id="__WORKFLOW_ID___local",
    #     endpoint="local://__WORKFLOW_ID__",
    # )
    # register_server(server)
    # register_tool(
    #     MCPTool(
    #         tool_id="sample_tool",
    #         server_id=server.server_id,
    #         description="설명을 추가하세요.",
    #         input_schema={"type": "object", "properties": {}},
    #     )
    # )
    # register_handler("sample_tool", lambda **kwargs: kwargs)
    return None
