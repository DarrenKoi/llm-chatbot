"""list_conversations 기능을 백엔드별로 검증한다."""

import importlib
import time
from unittest.mock import MagicMock, patch

from api import config


def _fresh_module():
    import api.conversation_service as mod

    mod._backend = None
    importlib.reload(mod)
    return mod


class TestInMemoryListConversations:
    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_returns_only_caller_conversations(self):
        mod = _fresh_module()
        mod.append_message(
            "alice",
            {"role": "user", "content": "alpha"},
            conversation_id="c1",
            metadata={"source": "cube"},
        )
        mod.append_message(
            "alice",
            {"role": "user", "content": "beta"},
            conversation_id="c2",
            metadata={"source": "web"},
        )
        mod.append_message(
            "bob",
            {"role": "user", "content": "leak"},
            conversation_id="c1",
            metadata={"source": "cube"},
        )

        summaries = mod.list_conversations("alice")

        assert {summary.conversation_id for summary in summaries} == {"c1", "c2"}
        assert all(summary.user_id == "alice" for summary in summaries)
        sources = {summary.conversation_id: summary.source for summary in summaries}
        assert sources == {"c1": "cube", "c2": "web"}

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_orders_by_last_message_descending_and_includes_preview(self):
        mod = _fresh_module()
        mod.append_message("alice", {"role": "user", "content": "older"}, conversation_id="c1")
        mod.append_message("alice", {"role": "assistant", "content": "newer reply"}, conversation_id="c2")

        summaries = mod.list_conversations("alice")

        assert [summary.conversation_id for summary in summaries] == ["c2", "c1"]
        assert summaries[0].last_message_preview == "newer reply"
        assert summaries[0].last_message_role == "assistant"

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_limit_truncates_results(self):
        mod = _fresh_module()
        for i in range(5):
            mod.append_message("alice", {"role": "user", "content": f"m{i}"}, conversation_id=f"c{i}")

        summaries = mod.list_conversations("alice", limit=2)

        assert len(summaries) == 2

    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_empty_user_returns_empty_list(self):
        mod = _fresh_module()
        assert mod.list_conversations("nobody") == []


class TestLocalFileListConversations:
    @patch.object(config, "CONVERSATION_BACKEND", "local")
    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_returns_only_caller_conversations(self, tmp_path):
        with patch.object(config, "CONVERSATION_LOCAL_DIR", tmp_path):
            mod = _fresh_module()
            mod.append_message(
                "alice",
                {"role": "user", "content": "alpha"},
                conversation_id="c1",
                metadata={"source": "cube"},
            )
            mod.append_message(
                "alice",
                {"role": "assistant", "content": "beta"},
                conversation_id="c2",
                metadata={"source": "web"},
            )
            mod.append_message(
                "bob",
                {"role": "user", "content": "leak"},
                conversation_id="c1",
                metadata={"source": "cube"},
            )

            summaries = mod.list_conversations("alice")

            assert {summary.conversation_id for summary in summaries} == {"c1", "c2"}
            assert {summary.source for summary in summaries} == {"cube", "web"}

    @patch.object(config, "CONVERSATION_BACKEND", "local")
    @patch.object(config, "AFM_MONGO_URI", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_orders_by_last_message_descending(self, tmp_path):
        with patch.object(config, "CONVERSATION_LOCAL_DIR", tmp_path):
            mod = _fresh_module()
            mod.append_message("alice", {"role": "user", "content": "older"}, conversation_id="c1")
            time.sleep(0.005)
            mod.append_message("alice", {"role": "assistant", "content": "newer"}, conversation_id="c2")

            summaries = mod.list_conversations("alice")

            assert [summary.conversation_id for summary in summaries] == ["c2", "c1"]
            assert summaries[0].last_message_preview == "newer"


class TestMongoListConversations:
    @patch.object(config, "AFM_DB_NAME", "test-db")
    @patch.object(config, "AFM_MONGO_URI", "mongodb://fake:27017")
    def test_uses_aggregation_pipeline_and_maps_results(self):
        mock_col = MagicMock()
        mock_col.aggregate.return_value = iter(
            [
                {
                    "_id": "c2",
                    "last_message_at": "2026-04-25T10:00:00+00:00",
                    "last_message_role": "assistant",
                    "last_message_content": "newer",
                    "source": "web",
                },
                {
                    "_id": "c1",
                    "last_message_at": "2026-04-24T10:00:00+00:00",
                    "last_message_role": "user",
                    "last_message_content": "older",
                    "source": "cube",
                },
            ]
        )
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("api.mongo.get_mongo_client", return_value=mock_client):
            mod = _fresh_module()
            summaries = mod.list_conversations("alice", limit=10)

        assert [summary.conversation_id for summary in summaries] == ["c2", "c1"]
        assert summaries[0].source == "web"
        assert summaries[1].source == "cube"
        assert summaries[0].last_message_preview == "newer"
        pipeline = mock_col.aggregate.call_args.args[0]
        assert pipeline[0] == {"$match": {"user_id": "alice"}}
        assert pipeline[-1] == {"$limit": 10}
