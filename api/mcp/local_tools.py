"""로컬 Python 함수를 MCP 도구 핸들러로 등록·조회한다."""

from collections.abc import Callable
from typing import Any

ToolHandler = Callable[..., Any]

_HANDLERS: dict[str, ToolHandler] = {}


def register_handler(tool_id: str, handler: ToolHandler) -> None:
    """tool_id에 대응하는 로컬 핸들러를 등록한다."""

    _HANDLERS[tool_id] = handler


def get_handler(tool_id: str) -> ToolHandler | None:
    """등록된 로컬 핸들러를 반환한다. 없으면 None."""

    return _HANDLERS.get(tool_id)


def clear_handlers() -> None:
    """등록된 모든 핸들러를 제거한다 (테스트용)."""

    _HANDLERS.clear()
