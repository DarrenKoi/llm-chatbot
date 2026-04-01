"""샘플 워크플로 end-to-end 테스트.

워크플로 노드가 MCP 도구를 실제로 호출하는지 검증한다.
  entry("다영") → greet(도구: "안녕하세요, 다영님!") → shout(도구: 대문자 변환) → 완료
"""

from unittest.mock import patch

import pytest

from api.mcp import local_tools, registry as mcp_registry
from api.workflows.models import WorkflowState
from api.workflows.orchestrator import run_graph
from api.workflows.sample.graph import build_graph
from api.workflows.sample.tools import register_sample_tools


@pytest.fixture(autouse=True)
def _clean_mcp():
    """테스트 전후로 MCP 레지스트리와 로컬 핸들러를 정리한다."""

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()

    register_sample_tools()

    yield

    mcp_registry._SERVERS.clear()
    mcp_registry._TOOLS.clear()
    local_tools.clear_handlers()


def _make_state(workflow_id: str = "sample", node_id: str = "entry") -> WorkflowState:
    return WorkflowState(
        user_id="test_user",
        workflow_id=workflow_id,
        node_id=node_id,
        data={},
    )


# ── 개별 도구 호출 테스트 ──────────────────────────────────────

def test_greet_tool_returns_korean_greeting():
    """greet 도구가 한국어 인사말을 반환하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(MCPToolCall(tool_id="greet", arguments={"name": "다영"}))

    assert result.success is True
    assert result.output == "안녕하세요, 다영님!"


def test_uppercase_tool():
    """uppercase 도구가 대문자 변환하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(MCPToolCall(tool_id="uppercase", arguments={"text": "hello"}))

    assert result.success is True
    assert result.output == "HELLO"


# ── 워크플로 end-to-end 테스트 ─────────────────────────────────

def test_sample_workflow_calls_tools_and_completes():
    """entry → greet → shout 전체 흐름이 도구를 호출하며 완료되는지 확인한다."""

    state = _make_state()
    graph = build_graph()

    reply = run_graph(graph, state, "다영")

    # greet 도구 → "안녕하세요, 다영님!" → uppercase 도구 → 최종 결과
    assert reply == "안녕하세요, 다영님!".upper()
    assert state.status == "completed"
    assert state.data["user_name"] == "다영"
    assert state.data["greeting"] == "안녕하세요, 다영님!"
    assert state.data["final_output"] == "안녕하세요, 다영님!".upper()


def test_sample_workflow_with_english_name():
    """영어 이름으로도 동일하게 동작하는지 확인한다."""

    state = _make_state()
    graph = build_graph()

    reply = run_graph(graph, state, "Alice")

    assert reply == "안녕하세요, ALICE님!".upper()
    assert state.status == "completed"


def test_sample_workflow_node_progression():
    """노드가 entry → greet → shout 순서로 실행되는지 확인한다."""

    state = _make_state()
    graph = build_graph()
    visited = []

    original_nodes = graph["nodes"]
    wrapped = {}
    for name, fn in original_nodes.items():
        def _wrap(node_fn, node_name):
            def wrapper(s, msg):
                visited.append(node_name)
                return node_fn(s, msg)
            return wrapper
        wrapped[name] = _wrap(fn, name)
    graph["nodes"] = wrapped

    run_graph(graph, state, "테스트")

    assert visited == ["entry", "greet", "shout"]


# ── 도구 실패 처리 테스트 ──────────────────────────────────────

def test_tool_failure_returns_error_result():
    """도구 핸들러가 예외를 던지면 MCPToolResult.success=False가 되는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    # greet에 잘못된 인자 전달 (name 누락)
    result = execute_tool_call(MCPToolCall(tool_id="greet", arguments={}))

    assert result.success is False
    assert result.error  # 에러 메시지가 있어야 함


# ── handle_message 통합 테스트 ─────────────────────────────────

def test_handle_message_with_sample_workflow():
    """handle_message를 통해 sample 워크플로가 동작하는지 확인한다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    incoming = CubeIncomingMessage(
        user_id="test_integration",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        message="통합테스트",
    )

    with patch("api.workflows.orchestrator.load_state", return_value=None), \
         patch("api.workflows.orchestrator.save_state") as mock_save, \
         patch("api.workflows.orchestrator.DEFAULT_WORKFLOW_ID", "sample"):

        reply = handle_message(incoming)

    assert "통합테스트" in reply.upper()
    mock_save.assert_called_once()

    saved_state = mock_save.call_args[0][0]
    assert saved_state.status == "completed"
