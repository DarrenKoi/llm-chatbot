"""번역 예제 워크플로에서 사용하는 MCP 도구를 등록한다."""

from api.mcp.local_tools import register_handler
from api.mcp.models import MCPServerConfig, MCPTool
from api.mcp.registry import register_server, register_tool
from api.workflows.translator.translation_engine import translate_text


def _translate(text: str, target_language: str) -> dict[str, str]:
    """입력 언어를 감지하고 대상 언어로 번역한다."""

    return translate_text(text=text, target_language=target_language)


def register_translator_tools() -> None:
    """번역 예제용 MCP 서버·도구·핸들러를 등록한다."""

    server = MCPServerConfig(server_id="translator_example_local", endpoint="local://translator_example")
    register_server(server)

    register_tool(
        MCPTool(
            tool_id="translate_example",
            server_id="translator_example_local",
            description="한국어/영어/일본어 사이의 번역을 수행하는 devtools 예제 도구다.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "target_language": {"type": "string"},
                },
                "required": ["text", "target_language"],
            },
        )
    )

    register_handler("translate_example", _translate)
