from unittest.mock import MagicMock, patch

import pytest

from api import config
from api.workflows.langgraph_checkpoint import open_langgraph_checkpoint_mongo


def test_open_langgraph_checkpoint_mongo_requires_uri(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "")
    monkeypatch.setattr(config, "AFM_DB_NAME", "test-db")

    with pytest.raises(RuntimeError, match="AFM_MONGO_URI"):
        open_langgraph_checkpoint_mongo()


def test_open_langgraph_checkpoint_mongo_uses_afm_database(monkeypatch):
    sentinel_db = object()
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = sentinel_db

    monkeypatch.setattr(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    monkeypatch.setattr(config, "AFM_DB_NAME", "test-db")

    with patch("pymongo.MongoClient", return_value=mock_client) as mock_cls:
        result = open_langgraph_checkpoint_mongo()

    mock_cls.assert_called_once_with("mongodb://fake:27017", serverSelectionTimeoutMS=3000)
    mock_client.__getitem__.assert_called_once_with("test-db")
    assert result.client is mock_client
    assert result.database is sentinel_db
