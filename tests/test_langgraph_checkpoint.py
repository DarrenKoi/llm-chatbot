from unittest.mock import MagicMock, patch

import pytest

from api import config
from api.workflows.langgraph_checkpoint import (
    build_thread_id,
    get_checkpointer,
    validate_mongo_storage_config,
)


def test_build_thread_id_with_channel_id():
    assert build_thread_id("user1", "c1") == "user1::c1"


def test_build_thread_id_without_channel_id():
    assert build_thread_id("user1") == "user1"


def test_build_thread_id_with_empty_channel_id():
    assert build_thread_id("user1", "") == "user1"


def test_get_checkpointer_returns_memory_saver_when_no_mongo(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "")

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = get_checkpointer()
    assert isinstance(checkpointer, MemorySaver)


def test_get_checkpointer_returns_memory_saver_when_persistence_disabled(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "mongodb://fake:27017")

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = get_checkpointer(persistent=False)
    assert isinstance(checkpointer, MemorySaver)


def test_get_checkpointer_returns_mongo_saver_when_uri_set(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    monkeypatch.setattr(config, "AFM_DB_NAME", "test-db")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_COLLECTION_NAME", "test-checkpoints")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME", "test-checkpoint-writes")
    monkeypatch.setattr(config, "CHECKPOINT_TTL_SECONDS", 259200)

    mock_client = MagicMock()
    with (
        patch("api.mongo.get_mongo_client", return_value=mock_client),
        patch("langgraph.checkpoint.mongodb.MongoDBSaver", autospec=True) as mock_saver_cls,
    ):
        checkpointer = get_checkpointer()
        assert checkpointer is mock_saver_cls.return_value
        mock_saver_cls.assert_called_once_with(
            mock_client,
            db_name="test-db",
            checkpoint_collection_name="test-checkpoints",
            writes_collection_name="test-checkpoint-writes",
            ttl=259200,
        )


def test_validate_mongo_storage_config_rejects_duplicate_collection_names(monkeypatch):
    monkeypatch.setattr(config, "CONVERSATION_COLLECTION_NAME", "shared")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_COLLECTION_NAME", "shared")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME", "cube_checkpoint_writes")

    with pytest.raises(ValueError, match="different MongoDB collections"):
        validate_mongo_storage_config()
