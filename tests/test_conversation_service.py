from unittest.mock import MagicMock, patch

import pytest

from api import config


class TestInMemoryBackend:
    """Test the in-memory conversation backend."""

    def _fresh_module(self):
        """Re-import conversation_service with reset global state."""
        import importlib

        import api.conversation_service as mod

        mod._backend = None
        importlib.reload(mod)
        return mod

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    def test_append_and_get(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "hi"})
        history = mod.get_history("user1")
        assert len(history) == 1
        assert history[0]["content"] == "hi"

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 3)
    def test_max_messages_trimming(self):
        mod = self._fresh_module()
        for i in range(5):
            mod.append_message("user1", {"role": "user", "content": f"msg{i}"})
        history = mod.get_history("user1")
        assert len(history) == 3
        assert history[0]["content"] == "msg2"

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_append_messages(self):
        mod = self._fresh_module()
        msgs = [
            {"role": "assistant", "content": "reply1"},
            {"role": "tool", "content": "result"},
        ]
        mod.append_messages("user1", msgs)
        history = mod.get_history("user1")
        assert len(history) == 2

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_history_is_scoped_by_conversation_id(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "alpha"}, conversation_id="c1")
        mod.append_message("user1", {"role": "assistant", "content": "beta"}, conversation_id="c2")

        assert mod.get_history("user1", conversation_id="c1") == [{"role": "user", "content": "alpha"}]
        assert mod.get_history("user1", conversation_id="c2") == [{"role": "assistant", "content": "beta"}]

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_empty_history(self):
        mod = self._fresh_module()
        assert mod.get_history("nonexistent") == []

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_returns_copy(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "hi"})
        h1 = mod.get_history("user1")
        h2 = mod.get_history("user1")
        assert h1 is not h2

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_get_applies_explicit_limit(self):
        mod = self._fresh_module()
        for i in range(5):
            mod.append_message("user1", {"role": "user", "content": f"msg{i}"})

        history = mod.get_history("user1", limit=2)

        assert [message["content"] for message in history] == ["msg3", "msg4"]

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_get_recent_returns_latest_messages_first(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "first"})
        mod.append_message("user2", {"role": "assistant", "content": "second"})

        recent = mod.get_recent_messages(limit=2)

        assert recent == [
            {"user_id": "user2", "conversation_id": "user2", "role": "assistant", "content": "second"},
            {"user_id": "user1", "conversation_id": "user1", "role": "user", "content": "first"},
        ]


class TestMongoBackend:
    """Test the MongoDB conversation backend with mocked pymongo."""

    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "CONVERSATION_TTL_SECONDS", 3600)
    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_append_inserts_document(self):
        mock_col = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            import importlib

            import api.conversation_service as mod

            mod._backend = None
            importlib.reload(mod)

            mod.append_message(
                "user1",
                {"role": "user", "content": "hello"},
                conversation_id="c1",
                metadata={"message_id": "m1", "channel_id": "c1"},
            )

            mock_col.insert_one.assert_called_once()
            doc = mock_col.insert_one.call_args[0][0]
            assert doc["user_id"] == "user1"
            assert doc["conversation_id"] == "c1"
            assert doc["role"] == "user"
            assert doc["content"] == "hello"
            assert doc["message_id"] == "m1"
            assert doc["channel_id"] == "c1"
            assert "created_at" in doc
            assert mock_col.create_index.call_count == 3

    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_get_returns_messages_in_order(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"role": "assistant", "content": "older"},
                    {"role": "user", "content": "newer"},
                ]
            )
        )

        mock_col = MagicMock()
        mock_col.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            import importlib

            import api.conversation_service as mod

            mod._backend = None
            importlib.reload(mod)

            history = mod.get_history("user1", conversation_id="c1")

            # Reversed from descending DB order → chronological
            assert history[0]["content"] == "newer"
            assert history[1]["content"] == "older"
            mock_col.find.assert_called_once_with(
                {"user_id": "user1", "conversation_id": "c1"},
                {"_id": 0, "role": 1, "content": 1},
            )
            mock_cursor.limit.assert_called_with(5)

    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_get_uses_explicit_limit(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(return_value=iter([]))

        mock_col = MagicMock()
        mock_col.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            import importlib

            import api.conversation_service as mod

            mod._backend = None
            importlib.reload(mod)

            mod.get_history("user1", limit=50)

            mock_cursor.limit.assert_called_with(50)

    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_get_recent_messages_uses_mongodb_query(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(return_value=iter([{"user_id": "user1", "role": "user", "content": "hello"}]))

        mock_col = MagicMock()
        mock_col.find.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            import importlib

            import api.conversation_service as mod

            mod._backend = None
            importlib.reload(mod)

            recent = mod.get_recent_messages(limit=50)

            assert recent == [{"user_id": "user1", "role": "user", "content": "hello"}]
            mock_col.find.assert_called_once_with(
                {},
                {"_id": 0, "user_id": 1, "conversation_id": 1, "role": 1, "content": 1},
            )
            mock_cursor.limit.assert_called_with(50)

    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_raises_when_configured_mongo_is_unavailable(self):
        from pymongo.errors import ConnectionFailure

        with patch("pymongo.MongoClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.admin.command.side_effect = ConnectionFailure("unreachable")
            mock_cls.return_value = mock_client

            import importlib

            import api.conversation_service as mod

            mod._backend = None
            importlib.reload(mod)

            with pytest.raises(mod.ConversationStoreError, match="MongoDB conversation store"):
                mod.append_message("user1", {"role": "user", "content": "hi"})
