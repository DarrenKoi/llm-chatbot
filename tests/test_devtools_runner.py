from devtools.workflow_runner import dev_orchestrator
from devtools.workflow_runner import routes as runner_routes
from devtools.workflow_runner.app import create_dev_app
from devtools.workflow_runner.dev_orchestrator import START_CHAT_ID
from devtools.workflow_runner.identity import get_default_dev_user_id


def test_get_default_dev_user_id_uses_pc_name(monkeypatch):
    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Alice MacBook-Pro")
    monkeypatch.delenv("COMPUTERNAME", raising=False)
    monkeypatch.delenv("HOSTNAME", raising=False)

    assert get_default_dev_user_id() == "dev_alice_macbook_pro"


def test_dev_runner_index_renders_default_user_id(monkeypatch):
    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Team Runner")
    app = create_dev_app()

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"dev_team_runner" in response.data


def test_dev_runner_send_uses_default_user_id_when_not_provided(monkeypatch):
    monkeypatch.setenv("DEV_RUNNER_PC_ID", "QA Box")
    app = create_dev_app()
    captured: dict[str, str] = {}

    def _fake_handle_dev_message(*, workflow_id: str, user_message: str, user_id: str) -> dict:
        captured["workflow_id"] = workflow_id
        captured["user_message"] = user_message
        captured["user_id"] = user_id
        return {"reply": "ok", "state": {}, "trace": []}

    monkeypatch.setattr(runner_routes, "handle_dev_message", _fake_handle_dev_message)

    response = app.test_client().post(
        "/api/send",
        json={"workflow_id": "sample_flow", "message": "hello"},
    )

    assert response.status_code == 200
    assert captured == {
        "workflow_id": "sample_flow",
        "user_message": "hello",
        "user_id": "dev_qa_box",
    }


def test_list_dev_workflow_ids_includes_start_chat(monkeypatch):
    """start_chat이 워크플로 목록 맨 앞에 포함된다."""

    monkeypatch.setattr(dev_orchestrator, "_dev_workflows", {"example_a": {}, "example_b": {}})

    ids = dev_orchestrator.list_dev_workflow_ids()

    assert ids[0] == START_CHAT_ID
    assert "example_a" in ids
    assert "example_b" in ids


def test_api_workflows_includes_start_chat(monkeypatch):
    """GET /api/workflows 응답에 start_chat이 포함된다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")
    monkeypatch.setattr(dev_orchestrator, "_dev_workflows", {"demo": {}})
    app = create_dev_app()

    response = app.test_client().get("/api/workflows")

    assert response.status_code == 200
    workflows = response.get_json()["workflows"]
    assert START_CHAT_ID in workflows


def test_handle_dev_message_trace_expands_node_sequence(monkeypatch):
    """stream chunk마다 trace step이 누적되어 어느 노드를 거쳤는지 보인다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")

    class _FakeSnapshot:
        def __init__(self, tasks=(), values=None):
            self.tasks = tasks
            self.values = values or {}
            self.next = ()

    class _FakeGraph:
        def get_state(self, _config):
            return _FakeSnapshot(values={"active_workflow": "translator"})

        def stream(self, _input, _config, *, stream_mode):
            assert stream_mode == "updates"
            yield {"entry": {}}
            yield {"classify": {"active_workflow": "translator"}}
            yield {"translator": {"pending_reply": "Hello"}}

    monkeypatch.setattr(dev_orchestrator, "_get_compiled_graph", lambda _wid: _FakeGraph())
    monkeypatch.setattr(
        dev_orchestrator.conversation_history,
        "append_message",
        lambda *a, **k: None,
    )

    result = dev_orchestrator.handle_dev_message(
        workflow_id=START_CHAT_ID,
        user_message="번역해줘",
        user_id="dev_test",
    )

    node_ids = [step["node_id"] for step in result["trace"]]
    assert node_ids == ["entry", "classify", "translator"]
    assert result["trace"][-1]["action"] == "complete"
    assert result["trace"][-1]["reply_preview"]


def test_handle_dev_message_trace_marks_interrupt(monkeypatch):
    """인터럽트 발생 시 마지막 trace step의 action이 interrupt가 된다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")

    class _FakeSnapshot:
        def __init__(self, tasks=(), values=None):
            self.tasks = tasks
            self.values = values or {}
            self.next = ()

    class _Task:
        interrupts = ()

    class _FakeGraph:
        def __init__(self):
            self._call_count = 0

        def get_state(self, _config):
            self._call_count += 1
            # 첫 호출(before_state)은 빈 상태, 두번째 호출(after_state)은 인터럽트
            if self._call_count == 1:
                return _FakeSnapshot()
            return _FakeSnapshot(tasks=(_Task(),), values={"pending_reply": "input?"})

        def stream(self, _input, _config, *, stream_mode):
            assert stream_mode == "updates"
            yield {"entry": {}}
            yield {"__interrupt__": ()}

    monkeypatch.setattr(dev_orchestrator, "_get_compiled_graph", lambda _wid: _FakeGraph())
    monkeypatch.setattr(
        dev_orchestrator.conversation_history,
        "append_message",
        lambda *a, **k: None,
    )

    result = dev_orchestrator.handle_dev_message(
        workflow_id=START_CHAT_ID,
        user_message="질문",
        user_id="dev_test",
    )

    assert [step["node_id"] for step in result["trace"]] == ["entry"]
    assert result["trace"][-1]["action"] == "interrupt"


def test_dev_start_chat_compiles_without_cross_import(monkeypatch):
    """devtools start_chat 그래프가 운영 그래프 cross-import 없이 컴파일된다."""

    dev_orchestrator._compiled_graphs.clear()
    dev_orchestrator._checkpointers.clear()

    graph = dev_orchestrator._get_compiled_graph(START_CHAT_ID)

    assert graph is not None
    assert graph is dev_orchestrator._compiled_graphs[START_CHAT_ID]


def test_dev_start_chat_routes_to_handoff_workflow_on_keyword_match(monkeypatch):
    """classify가 devtools handoff_keywords를 매칭하면 그 워크플로로 라우팅된다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")
    dev_orchestrator._compiled_graphs.clear()
    dev_orchestrator._checkpointers.clear()
    dev_orchestrator._thread_generations.clear()

    from langgraph.graph import END, StateGraph

    from devtools.workflows.start_chat import build_lg_graph as build_dev_start_chat
    from devtools.workflows.start_chat.lg_state import DevStartChatState

    def build_fake_handoff() -> StateGraph:
        s = StateGraph(DevStartChatState)
        s.add_node("fake_step", lambda state: {"pending_reply": "handoff received"})
        s.set_entry_point("fake_step")
        s.add_edge("fake_step", END)
        return s

    fake_workflows = {
        "start_chat": {
            "workflow_id": "start_chat",
            "build_lg_graph": build_dev_start_chat,
            "handoff_keywords": (),
        },
        "travel_planner_example": {
            "workflow_id": "travel_planner_example",
            "build_lg_graph": build_fake_handoff,
            "handoff_keywords": ("여행", "trip"),
        },
    }
    monkeypatch.setattr(dev_orchestrator, "_dev_workflows", fake_workflows)
    monkeypatch.setattr(
        dev_orchestrator.conversation_history,
        "append_message",
        lambda *a, **k: None,
    )

    result = dev_orchestrator.handle_dev_message(
        workflow_id=START_CHAT_ID,
        user_message="여행 계획 짜줘",
        user_id="dev_test_match",
    )

    node_ids = [step["node_id"] for step in result["trace"]]
    assert "classify" in node_ids
    assert "travel_planner_example" in node_ids
    assert "noop_reply" not in node_ids
    state_values = result["state"]["values"]
    assert state_values.get("active_workflow") == "travel_planner_example"
    assert state_values.get("handoff_match_reason") == "여행"


def test_dev_start_chat_falls_through_to_noop_reply_on_no_match(monkeypatch):
    """매칭 실패 시 noop_reply가 호출되고 active_workflow는 start_chat 그대로다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")
    dev_orchestrator._compiled_graphs.clear()
    dev_orchestrator._checkpointers.clear()
    dev_orchestrator._thread_generations.clear()

    monkeypatch.setattr(
        dev_orchestrator.conversation_history,
        "append_message",
        lambda *a, **k: None,
    )

    result = dev_orchestrator.handle_dev_message(
        workflow_id=START_CHAT_ID,
        user_message="일반 잡담",
        user_id="dev_test_nomatch",
    )

    node_ids = [step["node_id"] for step in result["trace"]]
    assert node_ids[-1] == "noop_reply"
    state_values = result["state"]["values"]
    assert state_values.get("active_workflow") == "start_chat"
    assert state_values.get("handoff_match_reason") == ""


def test_dev_runner_send_start_chat(monkeypatch):
    """start_chat 워크플로로 메시지 전송 시 handle_dev_message가 호출된다."""

    monkeypatch.setenv("DEV_RUNNER_PC_ID", "Test PC")
    app = create_dev_app()
    captured: dict[str, str] = {}

    def _fake_handle_dev_message(*, workflow_id: str, user_message: str, user_id: str) -> dict:
        captured["workflow_id"] = workflow_id
        return {"reply": "routed", "state": {"active_workflow": "translator"}, "trace": []}

    monkeypatch.setattr(runner_routes, "handle_dev_message", _fake_handle_dev_message)

    response = app.test_client().post(
        "/api/send",
        json={"workflow_id": START_CHAT_ID, "message": "번역해줘"},
    )

    assert response.status_code == 200
    assert captured["workflow_id"] == START_CHAT_ID
    data = response.get_json()
    assert data["state"]["active_workflow"] == "translator"
