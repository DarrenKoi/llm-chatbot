"""샘플 워크플로 노드 — 각 노드가 MCP 도구를 호출한다."""

import logging

from api.mcp.executor import execute_tool_call
from api.mcp.models import MCPToolCall
from api.workflows.models import NodeResult, WorkflowState

log = logging.getLogger(__name__)


def entry_node(state: WorkflowState, user_message: str) -> NodeResult:
    """사용자 이름을 저장하고 greet 노드로 이동한다."""

    del state
    return NodeResult(
        action="resume",
        next_node_id="greet",
        data_updates={"user_name": user_message.strip()},
    )


def greet_node(state: WorkflowState, user_message: str) -> NodeResult:
    """MCP greet 도구를 호출하여 인사말을 생성한다."""

    del user_message
    name = state.data.get("user_name", "세계")

    log.info("[sample] greet 도구 호출: name=%s", name)
    result = execute_tool_call(MCPToolCall(tool_id="greet", arguments={"name": name}))
    log.info("[sample] greet 도구 결과: %s", result)

    return NodeResult(
        action="resume",
        next_node_id="translate",
        data_updates={"greeting": result.output},
    )


def translate_node(state: WorkflowState, user_message: str) -> NodeResult:
    """MCP translate 도구를 호출하여 인사말을 번역한다."""

    del user_message
    greeting = state.data.get("greeting", "")

    log.info("[sample] translate 도구 호출: text=%s", greeting)
    result = execute_tool_call(MCPToolCall(tool_id="translate", arguments={"text": greeting}))
    log.info("[sample] translate 도구 결과: %s", result)

    translated = result.output.get("result", "") if isinstance(result.output, dict) else ""
    direction = ""
    if isinstance(result.output, dict):
        direction = f"{result.output['source']}→{result.output['target']}"

    return NodeResult(
        action="complete",
        reply=translated,
        data_updates={
            "translation_direction": direction,
            "translated": translated,
        },
    )
