# ruff: noqa: E501
"""번역 서비스 워크플로에서 사용하는 MCP 도구를 등록한다."""

from api.mcp.local_tools import register_handler
from api.mcp.models import MCPServerConfig, MCPTool
from api.mcp.registry import register_server, register_tool
from api.workflows.translator import TRANSLATOR_TOOL_TAGS
from api.workflows.translator.translation_engine import translate_text


def _translate(text: str, target_language: str) -> dict[str, str]:
    """입력 언어를 감지하고 대상 언어로 번역한다."""

    return translate_text(text=text, target_language=target_language)


def register_translator_tools() -> None:
    """번역 서비스용 MCP 서버·도구·핸들러를 등록한다."""

    server = MCPServerConfig(server_id="translator_local", endpoint="local://translator")
    register_server(server)

    register_tool(
        MCPTool(
            tool_id="translate",
            server_id="translator_local",
            description="한국어/영어/일본어/중국어/스페인어/프랑스어/독일어/베트남어/태국어 간 번역과 한국어 발음 표기를 제공한다.",
            tags=TRANSLATOR_TOOL_TAGS,
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

    register_handler("translate", _translate)
