"""MCP 서버, 도구, 실행 결과 모델을 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPServerConfig:
    """MCP 서버 연결 정보를 담는다."""

    server_id: str
    endpoint: str
    enabled: bool = True


@dataclass(slots=True)
class MCPTool:
    """등록된 MCP 도구 메타데이터다."""

    tool_id: str
    server_id: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPToolCall:
    """단일 MCP 도구 호출 요청이다."""

    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPToolResult:
    """단일 MCP 도구 호출 결과다."""

    tool_id: str
    output: Any = None
    success: bool = True
    error: str = ""
