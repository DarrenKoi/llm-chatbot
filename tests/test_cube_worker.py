from types import SimpleNamespace
from unittest.mock import patch

import pytest

from api.cube.models import CubeIncomingMessage, CubeQueuedMessage
from api.cube.service import CubeUpstreamError
from api.cube.worker import main, process_next_queued_message


@pytest.fixture(autouse=True)
def _stub_processed_marker(monkeypatch):
    # 기본값: 아직 처리되지 않은 메시지로 간주하고 마커 기록은 무시한다.
    # 마커 동작 자체를 검증하는 테스트는 개별적으로 재정의한다.
    monkeypatch.setattr("api.cube.worker.is_message_processed", lambda incoming: False)
    monkeypatch.setattr("api.cube.worker.mark_message_processed", lambda incoming: None)


def _queued_message(*, attempt: int = 0, enqueued_at: float | None = None) -> CubeQueuedMessage:
    return CubeQueuedMessage(
        incoming=CubeIncomingMessage(
            user_id="u1",
            user_name="tester",
            channel_id="c1",
            message_id="m1",
            message="hello",
        ),
        attempt=attempt,
        enqueued_at=enqueued_at,
    )


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_acknowledges_success(
    mock_dequeue,
    mock_process,
    mock_acknowledge,
    monkeypatch,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_dequeue.assert_called_once_with(timeout_seconds=0)
    mock_process.assert_called_once()
    mock_acknowledge.assert_called_once_with(_queued_message())


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.requeue_queued_message")
@patch("api.cube.worker.process_queued_message", side_effect=CubeUpstreamError("LLM reply generation failed."))
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_requeues_retryable_failure(
    mock_dequeue,
    mock_process,
    mock_requeue,
    mock_acknowledge,
    monkeypatch,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MAX_RETRIES", 3)
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_requeue.assert_called_once_with(_queued_message(), next_attempt=1)
    mock_acknowledge.assert_not_called()


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.requeue_queued_message")
@patch("api.cube.worker.process_queued_message", side_effect=CubeUpstreamError("LLM reply generation failed."))
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message(attempt=2))
def test_process_next_queued_message_drops_after_max_retries(
    mock_dequeue,
    mock_process,
    mock_requeue,
    mock_acknowledge,
    monkeypatch,
):
    failed_message = _queued_message(attempt=2)
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MAX_RETRIES", 3)
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_requeue.assert_not_called()
    mock_acknowledge.assert_called_once_with(failed_message)


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_skips_already_processed(
    mock_dequeue,
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    # 이미 처리 완료 마커가 있는 메시지는 재처리하지 않고 ack만 한다(재시작 복구 중복 방지).
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)
    monkeypatch.setattr("api.cube.worker.is_message_processed", lambda incoming: True)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_not_called()
    mock_acknowledge.assert_called_once_with(_queued_message())
    assert mock_log.call_args_list[0].args[0] == "cube_worker_message_duplicate_skipped"


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_marks_processed_on_success(
    mock_dequeue,
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)
    marked = []
    monkeypatch.setattr("api.cube.worker.mark_message_processed", lambda incoming: marked.append(incoming))

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_called_once()
    assert marked == [_queued_message().incoming]
    mock_acknowledge.assert_called_once_with(_queued_message())


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.requeue_queued_message")
@patch("api.cube.worker.process_queued_message", side_effect=CubeUpstreamError("LLM reply generation failed."))
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_does_not_mark_on_failure(
    mock_dequeue,
    mock_process,
    mock_requeue,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    # 처리 실패(재시도) 시에는 완료 마커를 남기면 안 된다.
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MAX_RETRIES", 3)
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)
    marked = []
    monkeypatch.setattr("api.cube.worker.mark_message_processed", lambda incoming: marked.append(incoming))

    assert process_next_queued_message(timeout_seconds=0) is True

    assert marked == []


_NOW = 1_000_000.0


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
def test_process_next_queued_message_drops_stale_message(
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 300)
    monkeypatch.setattr("api.cube.worker.time.time", lambda: _NOW)
    stale_message = _queued_message(enqueued_at=_NOW - 360)
    monkeypatch.setattr("api.cube.worker.dequeue_queued_message", lambda **_: stale_message)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_not_called()
    mock_acknowledge.assert_called_once_with(stale_message)
    assert mock_log.call_args_list[0].args[0] == "cube_worker_message_stale"
    assert mock_log.call_args_list[0].kwargs["age_seconds"] == 360.0


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
def test_process_next_queued_message_drops_message_without_timestamp(
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    # 구버전 페이로드(enqueued_at 없음)는 나이를 알 수 없어 stale로 폐기되어야 한다.
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 300)
    legacy_message = _queued_message(enqueued_at=None)
    monkeypatch.setattr("api.cube.worker.dequeue_queued_message", lambda **_: legacy_message)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_not_called()
    mock_acknowledge.assert_called_once_with(legacy_message)
    assert mock_log.call_args_list[0].args[0] == "cube_worker_message_stale"
    assert mock_log.call_args_list[0].kwargs["age_seconds"] is None


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
def test_process_next_queued_message_ttl_disabled_processes_old_message(
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    # TTL=0이면 아무리 오래된 메시지라도 정상 처리한다.
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 0)
    monkeypatch.setattr("api.cube.worker.time.time", lambda: _NOW)
    old_message = _queued_message(enqueued_at=_NOW - 99_999)
    monkeypatch.setattr("api.cube.worker.dequeue_queued_message", lambda **_: old_message)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_called_once()
    mock_acknowledge.assert_called_once_with(old_message)


@patch("api.cube.worker.log_activity")
@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
def test_process_next_queued_message_processes_fresh_message(
    mock_process,
    mock_acknowledge,
    mock_log,
    monkeypatch,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MESSAGE_TTL_SECONDS", 300)
    monkeypatch.setattr("api.cube.worker.time.time", lambda: _NOW)
    fresh_message = _queued_message(enqueued_at=_NOW - 10)
    monkeypatch.setattr("api.cube.worker.dequeue_queued_message", lambda **_: fresh_message)

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_process.assert_called_once()
    mock_acknowledge.assert_called_once_with(fresh_message)


@patch("api.workflows.langgraph_checkpoint.get_checkpointer")
@patch("api.workflows.langgraph_checkpoint.get_mongo_storage_collections")
def test_main_check_connections_reports_memory_fallback(
    mock_collections,
    mock_get_checkpointer,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr("api.cube.worker.config.AFM_MONGO_URI", "")
    monkeypatch.setattr("api.cube.worker.config.AFM_DB_NAME", "test-db")
    monkeypatch.setattr("api.cube.worker.config.CHECKPOINT_TTL_SECONDS", 259200)
    mock_collections.return_value = SimpleNamespace(
        conversation_history="cube_conversation_history",
        checkpoint="cube_checkpoints",
        checkpoint_writes="cube_checkpoint_writes",
    )
    mock_get_checkpointer.return_value = object()

    assert main(["--check-connections"]) == 1

    output = capsys.readouterr().out
    assert "AFM_MONGO_URI_set=False" in output
    assert "checkpointer_backend=memory" in output
    assert "checkpoint_persistence=disabled" in output


@patch("api.workflows.langgraph_checkpoint.get_checkpointer")
@patch("api.workflows.langgraph_checkpoint.get_mongo_storage_collections")
@patch("api.mongo.get_mongo_client")
def test_main_check_connections_reports_mongo_checkpointer(
    mock_get_mongo_client,
    mock_collections,
    mock_get_checkpointer,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr("api.cube.worker.config.AFM_MONGO_URI", "mongodb://fake:27017")
    monkeypatch.setattr("api.cube.worker.config.AFM_DB_NAME", "test-db")
    monkeypatch.setattr("api.cube.worker.config.CHECKPOINT_TTL_SECONDS", 259200)
    mock_collections.return_value = SimpleNamespace(
        conversation_history="cube_conversation_history",
        checkpoint="cube_checkpoints",
        checkpoint_writes="cube_checkpoint_writes",
    )

    conversation_collection = _FakeCollection("test-db.cube_conversation_history", count=3)
    checkpoint_collection = _FakeCollection(
        "test-db.cube_checkpoints",
        count=2,
        latest={
            "thread_id": "u1::c1",
            "checkpoint_ns": "",
            "checkpoint_id": "checkpoint-2",
        },
    )
    writes_collection = _FakeCollection("test-db.cube_checkpoint_writes", count=4)
    mock_get_mongo_client.return_value = _FakeMongoClient(
        {
            "cube_conversation_history": conversation_collection,
            "cube_checkpoints": checkpoint_collection,
            "cube_checkpoint_writes": writes_collection,
        }
    )
    mock_get_checkpointer.return_value = SimpleNamespace(
        checkpoint_collection=checkpoint_collection,
        writes_collection=writes_collection,
        ttl=259200,
    )

    assert main(["--check-connections"]) == 0

    output = capsys.readouterr().out
    assert "mongo_ping=ok" in output
    assert "conversation_count=3" in output
    assert "checkpointer_backend=mongodb" in output
    assert "checkpoint_count=2" in output
    assert "writes_count=4" in output
    assert "latest_checkpoint=thread_id=u1::c1 checkpoint_ns= checkpoint_id=checkpoint-2" in output


class _FakeMongoClient:
    def __init__(self, collections):
        self.admin = SimpleNamespace(command=lambda command: {"ok": 1})
        self._db = _FakeDatabase(collections)

    def __getitem__(self, name):
        return self._db


class _FakeDatabase:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]


class _FakeCollection:
    def __init__(self, full_name: str, *, count: int, latest: dict | None = None):
        self.full_name = full_name
        self._count = count
        self._latest = latest

    def count_documents(self, query):
        return self._count

    def find_one(self, query, projection=None, sort=None):
        return self._latest
