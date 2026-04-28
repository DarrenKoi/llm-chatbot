def test_mcp_package_exports_public_api():
    from api.mcp import (
        MCPError,
        MCPExecutionError,
        MCPRegistryError,
        MCPServerConfig,
        MCPTool,
        MCPToolCall,
        MCPToolResult,
        clear_handlers,
        execute_tool_call,
        execute_tool_calls,
        get_handler,
        get_server,
        get_tool,
        list_tools,
        normalize_tags,
        register_handler,
        register_server,
        register_tool,
    )

    assert MCPError
    assert MCPExecutionError
    assert MCPRegistryError
    assert MCPServerConfig
    assert MCPTool
    assert MCPToolCall
    assert MCPToolResult
    assert clear_handlers
    assert execute_tool_call
    assert execute_tool_calls
    assert get_handler
    assert get_server
    assert get_tool
    assert list_tools
    assert normalize_tags
    assert register_handler
    assert register_server
    assert register_tool


def test_mcp_package_still_allows_submodule_imports():
    from api.mcp import local_tools
    from api.mcp import registry as mcp_registry

    assert local_tools.clear_handlers
    assert mcp_registry.list_tools
