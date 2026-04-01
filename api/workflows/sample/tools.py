"""샘플 워크플로에서 사용하는 MCP 도구를 등록한다."""

import re

from api.mcp.local_tools import register_handler
from api.mcp.models import MCPServerConfig, MCPTool
from api.mcp.registry import register_server, register_tool

_KOREAN_CHAR = re.compile(r"[\uac00-\ud7a3]")

# ---------------------------------------------------------------------------
# 스텁 번역 사전 (테스트·데모용)
# 실제 구현 시 LLM 또는 번역 API로 교체한다.
# ---------------------------------------------------------------------------

_KO_TO_EN: dict[str, str] = {
    "안녕하세요": "Hello",
    "감사합니다": "Thank you",
    "좋은 아침입니다": "Good morning",
}

_EN_TO_KO: dict[str, str] = {v: k for k, v in _KO_TO_EN.items()}


# ---------------------------------------------------------------------------
# 로컬 핸들러 (실제 로직)
# ---------------------------------------------------------------------------

def _greet(name: str) -> str:
    """이름을 받아 인사말을 반환한다."""
    return f"안녕하세요, {name}님!"


def _translate(text: str) -> dict[str, str]:
    """텍스트의 언어를 감지하고 번역한다.

    한국어 → 영어, 영어 → 한국어 방향을 자동 감지한다.
    스텁 구현: 사전에 없는 문장은 방향 태그와 함께 반환한다.
    """

    if _KOREAN_CHAR.search(text):
        translated = _KO_TO_EN.get(text, f"[Translated to EN] {text}")
        return {"source": "ko", "target": "en", "result": translated}

    translated = _EN_TO_KO.get(text, f"[KO로 번역됨] {text}")
    return {"source": "en", "target": "ko", "result": translated}


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
        tool_id="translate",
        server_id="sample_local",
        description="한국어↔영어 번역. 언어를 자동 감지하여 반대 언어로 번역한다.",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    ))

    register_handler("greet", _greet)
    register_handler("translate", _translate)
