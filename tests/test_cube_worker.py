from types import SimpleNamespace
from unittest.mock import patch

from api.cube.models import CubeIncomingMessage, CubeQueuedMessage
from api.cube.service import CubeUpstreamError
from api.cube.worker import main, process_next_queued_message


def _queued_message(*, attempt: int = 0) -> CubeQueuedMessage:
    return CubeQueuedMessage(
        incoming=CubeIncomingMessage(
            user_id="u1",
            user_name="tester",
            channel_id="c1",
            message_id="m1",
            message="hello",
        ),
        attempt=attempt,
    )


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_acknowledges_success(
    mock_dequeue,
    mock_process,
    mock_acknowledge,
):
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

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_requeue.assert_not_called()
    mock_acknowledge.assert_called_once_with(failed_message)


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
