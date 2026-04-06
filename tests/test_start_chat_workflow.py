"""start_chat 워크플로 테스트.

Approach A 검증:
  - casual 의도 → start_chat 내부에서 직접 처리 (entry→classify→retrieve→plan→generate)
  - specific 의도 → handoff → 대상 워크플로 실행 → 스택 복귀
"""

from unittest.mock import patch

import pytest

from api.workflows.models import NodeResult, WorkflowState
from api.workflows.orchestrator import run_graph, _handle_handoff
from api.workflows.chart_maker.graph import build_graph as build_chart_maker_graph
from api.workflows.start_chat.graph import build_graph
from api.workflows.start_chat.nodes import entry_node
from api.workflows.start_chat.state import StartChatWorkflowState

_LLM_MOCK_TARGET = "api.workflows.start_chat.agent.executor.generate_reply"
_HISTORY_MOCK_TARGET = "api.workflows.start_chat.agent.executor.get_history"


def _make_state(
    *,
    detected_intent: str = "start_chat",
    node_id: str = "entry",
) -> StartChatWorkflowState:
    return StartChatWorkflowState(
        user_id="test_user",
        workflow_id="start_chat",
        node_id=node_id,
        detected_intent=detected_intent,
        data={},
    )


def _mock_llm_and_history(llm_reply="mock LLM 응답"):
    """LLM과 대화 이력 mock을 함께 적용하는 컨텍스트 매니저를 반환한다."""
    return (
        patch(_LLM_MOCK_TARGET, return_value=llm_reply),
        patch(_HISTORY_MOCK_TARGET, return_value=[]),
    )


# ── casual 의도: start_chat 내부 직접 처리 ─────────────────────

def test_start_chat_casual_follows_linear_flow():
    """casual 의도 시 entry→classify→retrieve→plan→generate 순서로 실행된다."""

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

    mock_llm, mock_history = _mock_llm_and_history()
    with mock_llm, mock_history:
        reply = run_graph(graph, state, "안녕하세요")

    assert visited == ["entry", "classify", "retrieve_context", "plan_response", "generate_reply"]
    assert reply == "mock LLM 응답"
    assert state.status == "completed"


def test_start_chat_casual_generates_reply():
    """casual 의도 시 LLM이 호출되어 응답을 생성한다."""

    state = _make_state()
    graph = build_graph()

    mock_llm, mock_history = _mock_llm_and_history("오늘 좋은 하루 되세요!")
    with mock_llm as m_llm, mock_history:
        reply = run_graph(graph, state, "오늘 뭐 해?")

    assert reply == "오늘 좋은 하루 되세요!"
    m_llm.assert_called_once()
    assert state.status == "completed"


def test_entry_node_loads_profile_into_state(mocker):
    state = _make_state()
    profile = mocker.Mock()
    profile.source = "profile_api"
    profile.to_prompt_text.return_value = "- 이름: 홍길동"

    mocker.patch("api.workflows.start_chat.nodes.load_user_profile", return_value=profile)

    result = entry_node(state, "안녕하세요")

    assert result.action == "resume"
    assert result.next_node_id == "classify"
    assert result.data_updates == {
        "profile_loaded": True,
        "profile_source": "profile_api",
        "profile_summary": "- 이름: 홍길동",
    }


def test_entry_node_handles_missing_profile(mocker):
    state = _make_state()
    mocker.patch("api.workflows.start_chat.nodes.load_user_profile", return_value=None)

    result = entry_node(state, "안녕하세요")

    assert result.data_updates == {
        "profile_loaded": False,
        "profile_source": "unavailable",
        "profile_summary": "",
    }


# ── classify 노드 분기 테스트 ──────────────────────────────────

def test_classify_returns_handoff_for_chart_maker():
    """chart_maker 의도 시 handoff action을 반환한다."""

    from api.workflows.start_chat.nodes import classify_intent_node

    state = _make_state(detected_intent="chart_maker")
    result = classify_intent_node(state, "차트 만들어줘")

    assert result.action == "handoff"
    assert result.next_workflow_id == "chart_maker"


def test_classify_returns_resume_for_casual():
    """casual 의도 시 resume action으로 retrieve_context를 이어간다."""

    from api.workflows.start_chat.nodes import classify_intent_node

    state = _make_state(detected_intent="start_chat")
    result = classify_intent_node(state, "안녕")

    assert result.action == "resume"
    assert result.next_node_id == "retrieve_context"


@pytest.mark.parametrize(
    ("message", "expected_workflow_id"),
    [
        ("차트 만들어줘", "chart_maker"),
        ("여행 계획 짜줘", "travel_planner"),
    ],
)
def test_classify_handoff_targets(message, expected_workflow_id):
    """등록된 업무 요청 메시지에 대해 handoff가 동작한다."""

    from api.workflows.start_chat.nodes import classify_intent_node

    state = _make_state()
    result = classify_intent_node(state, message)

    assert result.action == "handoff"
    assert result.next_workflow_id == expected_workflow_id
    assert state.detected_intent == expected_workflow_id


# ── 오케스트레이터 handoff 테스트 ──────────────────────────────

def test_orchestrator_handoff_switches_workflow():
    """handoff 시 스택에 현재 위치를 저장하고 대상 워크플로로 전환한다."""

    state = _make_state(detected_intent="chart_maker")
    graph = build_graph()

    reply = run_graph(graph, state, "차트 만들어줘")

    # chart_maker 워크플로가 실행되었어야 함
    # chart_maker의 entry_node는 wait을 반환하므로 워크플로가 완료되지 않음
    # → 스택에 start_chat 위치가 남아있어야 함
    assert state.workflow_id == "chart_maker"
    assert len(state.stack) == 1
    assert state.stack[0]["workflow_id"] == "start_chat"


def test_handoff_completes_and_returns_to_parent():
    """대상 워크플로가 완료되면 스택에서 복귀한다."""

    state = WorkflowState(
        user_id="test_user",
        workflow_id="start_chat",
        node_id="classify",
        data={},
        stack=[],
    )

    # 즉시 완료하는 가짜 워크플로
    def instant_done_node(s, msg):
        return NodeResult(action="complete", reply="완료!")

    fake_graph = {
        "workflow_id": "fake_target",
        "entry_node_id": "entry",
        "nodes": {"entry": instant_done_node},
    }

    fake_workflow_def = {
        "workflow_id": "fake_target",
        "entry_node_id": "entry",
        "build_graph": lambda: fake_graph,
    }

    handoff_result = NodeResult(action="handoff", next_workflow_id="fake_target")

    with patch("api.workflows.orchestrator.get_workflow", return_value=fake_workflow_def):
        reply = _handle_handoff(state, handoff_result, "테스트")

    assert reply == "완료!"
    # 복귀: 다음 사용자 턴을 받을 수 있도록 start_chat entry로 초기화되어야 함
    assert state.workflow_id == "start_chat"
    assert state.node_id == "entry"
    assert state.status == "active"
    assert len(state.stack) == 0


def test_handoff_without_target_returns_empty():
    """handoff 대상이 없으면 빈 문자열을 반환한다."""

    state = _make_state()
    result = NodeResult(action="handoff", next_workflow_id=None)

    reply = _handle_handoff(state, result, "테스트")

    assert reply == ""


def test_handed_off_workflow_uses_target_state_and_returns_to_start_chat():
    """handoff된 워크플로가 전용 상태를 유지하고 종료 후 start_chat으로 복귀한다."""

    state = _make_state(detected_intent="chart_maker")

    first_reply = run_graph(build_graph(), state, "차트 만들어줘")

    assert first_reply == ""
    assert state.workflow_id == "chart_maker"
    assert state.node_id == "collect_requirements"
    assert len(state.stack) == 1

    second_reply = run_graph(build_chart_maker_graph(), state, "line")

    assert second_reply == ""
    assert state.workflow_id == "chart_maker"
    assert state.node_id == "build_spec"
    assert getattr(state, "chart_type") == "line"

    final_reply = run_graph(build_chart_maker_graph(), state, "계속")

    assert final_reply == "차트 명세 생성 스켈레톤입니다."
    assert state.workflow_id == "start_chat"
    assert state.node_id == "entry"
    assert state.status == "active"
    assert state.stack == []


# ── handle_message 통합 테스트 ─────────────────────────────────

def test_handle_message_uses_start_chat_as_default():
    """handle_message가 start_chat을 기본 워크플로로 사용한다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    incoming = CubeIncomingMessage(
        user_id="test_default",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        message="안녕",
    )

    mock_llm, mock_history = _mock_llm_and_history("안녕하세요!")
    with patch("api.workflows.orchestrator.load_state", return_value=None), \
         patch("api.workflows.orchestrator.save_state") as mock_save, \
         mock_llm, mock_history:

        reply = handle_message(incoming)

    assert reply == "안녕하세요!"
    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert saved_state.workflow_id == "start_chat"


def test_handle_message_routes_chart_request_from_user_message():
    """실제 사용자 메시지에서 차트 워크플로 handoff가 결정된다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    incoming = CubeIncomingMessage(
        user_id="test_handoff",
        user_name="tester",
        channel_id="c1",
        message_id="m_chart",
        message="차트 만들어줘",
    )

    with patch("api.workflows.orchestrator.load_state", return_value=None), \
         patch("api.workflows.orchestrator.save_state") as mock_save:
        reply = handle_message(incoming)

    assert reply == "[chart_maker] 처리 완료."
    saved_state = mock_save.call_args[0][0]
    assert saved_state.workflow_id == "chart_maker"
    assert saved_state.node_id == "collect_requirements"
    assert saved_state.status == "waiting_user_input"
    assert saved_state.data["detected_intent"] == "chart_maker"
    assert saved_state.stack == [{"workflow_id": "start_chat", "node_id": "classify"}]


def test_handle_message_restarts_completed_start_chat_session():
    """완료된 start_chat 상태는 다음 턴 전에 entry부터 다시 시작해야 한다."""

    from api.cube.models import CubeIncomingMessage
    from api.workflows.orchestrator import handle_message

    completed_state = StartChatWorkflowState(
        user_id="test_restart",
        workflow_id="start_chat",
        node_id="generate_reply",
        status="completed",
        detected_intent="chart_maker",
        retrieved_contexts=["stale"],
        agent_plan=["old-plan"],
        data={
            "detected_intent": "chart_maker",
            "retrieved_contexts": ["stale"],
            "agent_plan": ["old-plan"],
        },
    )
    incoming = CubeIncomingMessage(
        user_id="test_restart",
        user_name="tester",
        channel_id="c1",
        message_id="m2",
        message="후속 질문",
    )

    mock_llm, mock_history = _mock_llm_and_history("후속 답변입니다")
    with patch("api.workflows.orchestrator.load_state", return_value=completed_state), \
         patch("api.workflows.orchestrator.save_state") as mock_save, \
         mock_llm, mock_history:
        reply = handle_message(incoming)

    assert reply == "후속 답변입니다"
    mock_save.assert_called_once()
    saved_state = mock_save.call_args[0][0]
    assert saved_state.workflow_id == "start_chat"
    assert saved_state.status == "completed"
    assert saved_state.data["detected_intent"] == "start_chat"
    assert saved_state.data["latest_user_message"] == "후속 질문"
    assert saved_state.stack == []
