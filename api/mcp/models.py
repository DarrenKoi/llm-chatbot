"""MCP 서버, 도구, 실행 결과 모델을 정의한다."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


def _normalize_tags(raw_tags: object) -> tuple[str, ...]:
    if raw_tags in (None, ""):
        return ()

    if isinstance(raw_tags, str):
        candidates = [raw_tags]
    elif isinstance(raw_tags, Iterable):
        candidates = raw_tags
    else:
        raise TypeError("tags는 문자열 또는 문자열 iterable이어야 합니다.")

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in candidates:
        value = str(tag).strip().lower()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)


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
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.tags = _normalize_tags(self.tags)


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
