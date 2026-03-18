import json
from unittest.mock import patch, MagicMock

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

    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    def test_append_and_get(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "hi"})
        history = mod.get_history("user1")
        assert len(history) == 1
        assert history[0]["content"] == "hi"

    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 3)
    def test_max_messages_trimming(self):
        mod = self._fresh_module()
        for i in range(5):
            mod.append_message("user1", {"role": "user", "content": f"msg{i}"})
        history = mod.get_history("user1")
        assert len(history) == 3
        assert history[0]["content"] == "msg2"

    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "")
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

    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_empty_history(self):
        mod = self._fresh_module()
        assert mod.get_history("nonexistent") == []

    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "")
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 20)
    def test_returns_copy(self):
        mod = self._fresh_module()
        mod.append_message("user1", {"role": "user", "content": "hi"})
        h1 = mod.get_history("user1")
        h2 = mod.get_history("user1")
        assert h1 is not h2


class TestRedisBackend:
    """Test the Redis conversation backend with mocked Redis client."""

    @patch.object(config, "CONVERSATION_TTL_SECONDS", 3600)
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "REDIS_FALLBACK_URL", "")
    @patch.object(config, "REDIS_URL", "redis://fake:6379")
    def test_append_and_get(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch("redis.from_url", return_value=mock_redis):
            import importlib
            import api.conversation_service as mod
            mod._backend = None
            importlib.reload(mod)

            mod.append_message("user1", {"role": "user", "content": "hello"})

            # Redis.set should have been called with JSON
            mock_redis.set.assert_called_once()
            call_args = mock_redis.set.call_args
            stored = json.loads(call_args[0][1])
            assert len(stored) == 1
            assert stored[0]["content"] == "hello"
            assert call_args[1]["ex"] == 3600

    @patch.object(config, "CONVERSATION_TTL_SECONDS", 3600)
    @patch.object(config, "CONVERSATION_MAX_MESSAGES", 5)
    @patch.object(config, "REDIS_FALLBACK_URL", "redis://secondary:6379/0")
    @patch.object(config, "REDIS_URL", "redis://primary:6379/0")
    def test_fallback_to_secondary_when_primary_fails(self):
        primary = MagicMock()
        primary.ping.side_effect = RuntimeError("primary down")

        secondary = MagicMock()
        secondary.get.return_value = None

        with patch("redis.from_url", side_effect=[primary, secondary]) as mock_from_url:
            import importlib
            import api.conversation_service as mod
            mod._backend = None
            importlib.reload(mod)

            mod.append_message("user1", {"role": "user", "content": "hello"})

            assert mock_from_url.call_count == 2
            secondary.set.assert_called_once()
