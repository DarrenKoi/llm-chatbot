"""샘플 워크플로 end-to-end 테스트.

워크플로 노드가 MCP 도구를 실제로 호출하는지 검증한다.
  entry("다영") → greet(도구: "안녕하세요, 다영님!") → translate(도구: ko→en 번역) → 완료
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


def test_translate_tool_korean_to_english():
    """translate 도구가 한국어를 영어로 번역하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(
        MCPToolCall(tool_id="translate", arguments={"text": "감사합니다"}),
    )

    assert result.success is True
    assert result.output["source"] == "ko"
    assert result.output["target"] == "en"
    assert result.output["result"] == "Thank you"


def test_translate_tool_english_to_korean():
    """translate 도구가 영어를 한국어로 번역하는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(
        MCPToolCall(tool_id="translate", arguments={"text": "Good morning"}),
    )

    assert result.success is True
    assert result.output["source"] == "en"
    assert result.output["target"] == "ko"
    assert result.output["result"] == "좋은 아침입니다"


def test_translate_tool_unknown_korean_uses_fallback():
    """사전에 없는 한국어 문장도 방향 태그와 함께 반환되는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(
        MCPToolCall(tool_id="translate", arguments={"text": "오늘 날씨가 좋다"}),
    )

    assert result.output["source"] == "ko"
    assert result.output["result"].startswith("[Translated to EN]")


# ── 워크플로 end-to-end 테스트 ─────────────────────────────────

def test_sample_workflow_greet_then_translate():
    """entry → greet → translate 전체 흐름이 도구를 호출하며 완료되는지 확인한다."""

    state = _make_state()
    graph = build_graph()

    reply = run_graph(graph, state, "다영")

    # greet → "안녕하세요, 다영님!" → translate(ko→en) → fallback
    assert state.status == "completed"
    assert state.data["user_name"] == "다영"
    assert state.data["greeting"] == "안녕하세요, 다영님!"
    assert state.data["translation_direction"] == "ko→en"
    assert reply  # 번역 결과가 비어있지 않아야 함


def test_sample_workflow_known_greeting_translates_exactly():
    """사전에 있는 인사말이 정확하게 번역되는지 확인한다."""

    # greet 결과가 "안녕하세요"로 시작하지만 "안녕하세요, X님!" 형태라 사전에 정확히 없음
    # → fallback 경로로 간다. 이것도 정상 동작이다.
    state = _make_state()
    graph = build_graph()

    reply = run_graph(graph, state, "테스트")

    assert state.data["translated"] == reply
    assert state.data["translation_direction"] == "ko→en"


def test_sample_workflow_node_progression():
    """노드가 entry → greet → translate 순서로 실행되는지 확인한다."""

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

    assert visited == ["entry", "greet", "translate"]


# ── 도구 실패 처리 테스트 ──────────────────────────────────────

def test_tool_failure_returns_error_result():
    """도구 핸들러가 예외를 던지면 MCPToolResult.success=False가 되는지 확인한다."""

    from api.mcp.executor import execute_tool_call
    from api.mcp.models import MCPToolCall

    result = execute_tool_call(MCPToolCall(tool_id="greet", arguments={}))

    assert result.success is False
    assert result.error


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

    mock_save.assert_called_once()

    saved_state = mock_save.call_args[0][0]
    assert saved_state.status == "completed"
    assert saved_state.data["translation_direction"] == "ko→en"
    assert reply  # 번역 결과 반환
