import json
from unittest.mock import patch

from api.cube.models import CubeIncomingMessage, CubeQueuedMessage
from api.cube.queue import _RedisCubeQueueBackend, requeue_queued_message


def _incoming() -> CubeIncomingMessage:
    return CubeIncomingMessage(
        user_id="u1",
        user_name="tester",
        channel_id="c1",
        message_id="m1",
        message="안녕하세요",
    )


def test_serialize_roundtrip_preserves_enqueued_at():
    message = CubeQueuedMessage(incoming=_incoming(), attempt=2, enqueued_at=1_700_000_000.5)
    raw = _RedisCubeQueueBackend._serialize_message(message)

    payload = json.loads(raw)
    assert payload["enqueued_at"] == 1_700_000_000.5
    assert "raw" not in payload  # raw는 직렬화되지 않는다

    restored = _RedisCubeQueueBackend._deserialize_message(raw)
    assert restored.attempt == 2
    assert restored.enqueued_at == 1_700_000_000.5
    assert restored.raw == raw  # 원본 페이로드가 보존된다


def test_deserialize_legacy_payload_without_enqueued_at():
    # enqueued_at 필드가 없는 구버전 페이로드도 파싱되어야 한다(enqueued_at=None).
    legacy_raw = json.dumps(
        {
            "incoming": {
                "user_id": "u1",
                "user_name": "tester",
                "channel_id": "c1",
                "message_id": "m1",
                "message": "hi",
            },
            "attempt": 0,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    restored = _RedisCubeQueueBackend._deserialize_message(legacy_raw)
    assert restored.enqueued_at is None
    assert restored.raw == legacy_raw


class _RecordingRedis:
    def __init__(self):
        self.lrem_calls = []

    def lrem(self, key, count, value):
        self.lrem_calls.append((key, count, value))
        return 1


def test_acknowledge_removes_by_original_raw_payload():
    # 직렬화 형식이 바뀌어도 큐에 들어있던 원본 문자열로 LREM 해야 한다.
    original_raw = '{"incoming":{"different":"format"},"legacy":true}'
    message = CubeQueuedMessage(incoming=_incoming(), attempt=0, enqueued_at=123.0, raw=original_raw)
    backend = _RedisCubeQueueBackend(_RecordingRedis())

    backend.acknowledge(message)

    assert backend._r.lrem_calls[0][2] == original_raw


class _MarkerRedis:
    def __init__(self, *, existing: set[str] | None = None):
        self.set_calls = []
        self._existing = existing or set()

    def set(self, name, value, ex=None):
        self.set_calls.append((name, value, ex))
        self._existing.add(name)
        return True

    def exists(self, name):
        return 1 if name in self._existing else 0


def test_processed_key_format():
    assert _RedisCubeQueueBackend._processed_key(_incoming()) == "cube:incoming:done:u1:m1"


def test_processed_key_none_without_message_id():
    incoming = CubeIncomingMessage(user_id="u1", user_name="t", channel_id="c1", message_id="", message="hi")
    assert _RedisCubeQueueBackend._processed_key(incoming) is None


def test_mark_processed_sets_key_with_ttl(monkeypatch):
    monkeypatch.setattr("api.cube.queue.config.CUBE_MESSAGE_PROCESSED_TTL_SECONDS", 7200)
    backend = _RedisCubeQueueBackend(_MarkerRedis())

    backend.mark_processed(_incoming())

    name, value, ex = backend._r.set_calls[0]
    assert name == "cube:incoming:done:u1:m1"
    assert value == "1"
    assert ex == 7200


def test_mark_processed_clamps_nonpositive_ttl(monkeypatch):
    # ex<=0은 redis SET에서 오류이므로, 오설정 시에도 마커가 조용히 비활성화되지 않게 하한(1)을 적용한다.
    monkeypatch.setattr("api.cube.queue.config.CUBE_MESSAGE_PROCESSED_TTL_SECONDS", 0)
    backend = _RedisCubeQueueBackend(_MarkerRedis())

    backend.mark_processed(_incoming())

    assert backend._r.set_calls[0][2] == 1


def test_is_processed_reflects_marker_presence():
    backend = _RedisCubeQueueBackend(_MarkerRedis())
    assert backend.is_processed(_incoming()) is False

    backend.mark_processed(_incoming())
    assert backend.is_processed(_incoming()) is True


def test_requeue_preserves_enqueued_at():
    original = CubeQueuedMessage(incoming=_incoming(), attempt=0, enqueued_at=42.0)
    captured = {}

    class _Backend:
        def requeue(self, current, replacement):
            captured["replacement"] = replacement

    with patch("api.cube.queue._get_backend", return_value=_Backend()):
        result = requeue_queued_message(original, next_attempt=1)

    assert result.attempt == 1
    assert result.enqueued_at == 42.0  # 재시도해도 나이 시계가 초기화되지 않는다
    assert captured["replacement"].enqueued_at == 42.0
