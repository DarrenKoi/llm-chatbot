"""MCP 인프라에서 사용하는 예외를 정의한다."""


class MCPError(RuntimeError):
    """MCP 관련 기본 예외다."""


class MCPRegistryError(MCPError):
    """레지스트리 조회 실패 예외다."""


class MCPExecutionError(MCPError):
    """도구 실행 실패 예외다."""
