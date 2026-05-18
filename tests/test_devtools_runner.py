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
