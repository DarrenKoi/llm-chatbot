"""샘플 워크플로에서 사용하는 MCP 도구를 등록한다."""

from api.mcp.local_tools import register_handler
from api.mcp.models import MCPTool
from api.mcp.registry import register_server, register_tool
from api.mcp.models import MCPServerConfig


# ---------------------------------------------------------------------------
# 로컬 핸들러 (실제 로직)
# ---------------------------------------------------------------------------

def _greet(name: str) -> str:
    """이름을 받아 인사말을 반환한다."""
    return f"안녕하세요, {name}님!"


def _uppercase(text: str) -> str:
    """텍스트를 대문자로 변환한다."""
    return text.upper()


# ---------------------------------------------------------------------------
# 등록
# ---------------------------------------------------------------------------

def register_sample_tools() -> None:
    """샘플 MCP 서버·도구·핸들러를 등록한다."""

    server = MCPServerConfig(server_id="sample_local", endpoint="local://sample")
    register_server(server)

    register_tool(MCPTool(
        tool_id="greet",
        server_id="sample_local",
        description="이름을 받아 인사말을 반환한다.",
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
    ))
    register_tool(MCPTool(
        tool_id="uppercase",
        server_id="sample_local",
        description="텍스트를 대문자로 변환한다.",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    ))

    register_handler("greet", _greet)
    register_handler("uppercase", _uppercase)
