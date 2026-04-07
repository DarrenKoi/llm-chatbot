from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from api import config, monitoring_service
from api.file_delivery import file_delivery_service


class _FakeListRedis:
    def __init__(self):
        self._lists: dict[str, list[str]] = {}
        self.closed = False

    def delete(self, *keys):
        for key in keys:
            self._lists.pop(key, None)

    def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    def rpoplpush(self, source, destination):
        items = self._lists.get(source, [])
        if not items:
            return None
        value = items.pop()
        self._lists.setdefault(destination, []).insert(0, value)
        return value

    def lrem(self, key, count, value):
        items = self._lists.get(key, [])
        removed = 0
        kept: list[str] = []
        for item in items:
            if item == value and (count == 0 or removed < count):
                removed += 1
                continue
            kept.append(item)
        self._lists[key] = kept
        return removed

    def close(self):
        self.closed = True


class _FakeLockRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self.closed = False

    def lock(self, name, timeout=None, blocking=False, thread_local=False):
        return _FakeRedisLock(self, name)

    def get(self, key):
        return self._store.get(key)

    def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)

    def close(self):
        self.closed = True


class _FakeRedisLock:
    def __init__(self, client: _FakeLockRedis, key: str):
        self._client = client
        self._key = key
        self._token = f"token:{key}"

    def acquire(self, blocking=False):
        if self._key in self._client._store:
            return False
        self._client._store[self._key] = self._token
        return True

    def release(self):
        self._client._store.pop(self._key, None)


class _FakeMetadataRedis:
    def __init__(self):
        self._values: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    def set(self, key, value, ex=None):
        self._values[key] = value

    def get(self, key):
        return self._values.get(key)

    def delete(self, key):
        self._values.pop(key, None)

    def sadd(self, key, value):
        self._sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self._sets.setdefault(key, set()).discard(value)

    def smembers(self, key):
        return set(self._sets.get(key, set()))


def test_check_daemon_component_reports_running_for_recent_heartbeat(monkeypatch, tmp_path):
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text(
        (
            '{"event":"cube_worker_started","timestamp":"2026-04-02T13:00:00+00:00","pid":101}\n'
            f'{{"event":"cube_worker_heartbeat","timestamp":"{datetime.now(UTC).isoformat()}","pid":101}}\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "ok"
    assert entry.status == "running"
    assert "pid=101" in entry.target


def test_check_daemon_component_reports_stale_for_old_heartbeat(monkeypatch, tmp_path):
    stale_timestamp = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text(
        f'{{"event":"scheduler_worker_heartbeat","timestamp":"{stale_timestamp}","pid":202}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Scheduler Worker Daemon",
        event_names=("scheduler_worker_heartbeat", "scheduler_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "error"
    assert entry.status == "stale"
    assert "pid=202" in entry.target


def test_check_daemon_component_reports_not_running_without_activity(monkeypatch, tmp_path):
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "error"
    assert entry.status == "not running"


def test_check_cube_queue_reports_working_for_queue_roundtrip(monkeypatch):
    fake_redis = _FakeListRedis()

    monkeypatch.setattr(config, "CUBE_QUEUE_REDIS_URL", "redis://queue")
    monkeypatch.setattr(config, "CUBE_QUEUE_NAME", "cube:incoming")
    monkeypatch.setattr(config, "CUBE_QUEUE_PROCESSING_NAME", "cube:incoming:processing")
    monkeypatch.setattr(monitoring_service, "_build_redis_client", lambda _url: fake_redis)

    entry = monitoring_service._check_cube_queue()

    assert entry.tone == "ok"
    assert entry.status == "working"
    assert entry.target == "cube:incoming / cube:incoming:processing"
    assert fake_redis.closed is True


def test_check_scheduler_lock_reports_working_for_lock_roundtrip(monkeypatch):
    fake_redis = _FakeLockRedis()

    monkeypatch.setattr(config, "SCHEDULER_REDIS_URL", "redis://scheduler")
    monkeypatch.setattr(config, "SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
    monkeypatch.setattr(config, "SCHEDULER_LOCK_TTL_SECONDS", 60)
    monkeypatch.setattr(monitoring_service, "_build_redis_client", lambda _url: fake_redis)

    entry = monitoring_service._check_scheduler_lock()

    assert entry.tone == "ok"
    assert entry.status == "working"
    assert entry.target == "scheduler:sknn_v3:*"
    assert fake_redis.closed is True


def test_check_file_delivery_metadata_reports_working_for_redis_backend(monkeypatch):
    backend = file_delivery_service._RedisMetadataBackend(_FakeMetadataRedis())

    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "redis://metadata")
    monkeypatch.setattr(file_delivery_service, "_metadata_backend", backend)

    entry = monitoring_service._check_file_delivery_metadata()

    assert entry.tone == "ok"
    assert entry.status == "working"
    assert entry.backend == "Redis"


def test_check_file_delivery_metadata_reports_fallback_for_memory_backend(monkeypatch):
    backend = file_delivery_service._InMemoryMetadataBackend()

    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(file_delivery_service, "_metadata_backend", backend)

    entry = monitoring_service._check_file_delivery_metadata()

    assert entry.tone == "warning"
    assert entry.status == "fallback"
    assert entry.backend == "Memory"


def test_check_langgraph_checkpoint_store_reports_connected(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "mongodb://user:secret@db-host:27017/")
    monkeypatch.setattr(config, "AFM_DB_NAME", "test-db")
    monkeypatch.setattr(config, "CONVERSATION_COLLECTION_NAME", "conversation_history")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_COLLECTION_NAME", "checkpoints")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME", "checkpoint_writes")
    monkeypatch.setattr(config, "CHECKPOINT_TTL_SECONDS", 259200)

    with patch("pymongo.MongoClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        entry = monitoring_service._check_langgraph_checkpoint_store()

    assert entry.tone == "ok"
    assert entry.status == "connected"
    assert "checkpoints / checkpoint_writes" in entry.target
    assert "TTL=259200초" in entry.detail


def test_check_mongo_conversation_store_reports_local_file_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONVERSATION_BACKEND", "local")
    monkeypatch.setattr(config, "CONVERSATION_LOCAL_DIR", tmp_path)

    entry = monitoring_service._check_mongo_conversation_store()

    assert entry.tone == "ok"
    assert entry.status == "connected"
    assert entry.backend == "Local File"
    assert entry.target == str(tmp_path)


def test_check_mongo_conversation_store_reports_memory_backend(monkeypatch):
    monkeypatch.setattr(config, "CONVERSATION_BACKEND", "memory")

    entry = monitoring_service._check_mongo_conversation_store()

    assert entry.tone == "warning"
    assert entry.status == "fallback"
    assert entry.backend == "Memory"


def test_check_langgraph_checkpoint_store_reports_config_error(monkeypatch):
    monkeypatch.setattr(config, "AFM_MONGO_URI", "mongodb://user:secret@db-host:27017/")
    monkeypatch.setattr(config, "CONVERSATION_COLLECTION_NAME", "shared")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_COLLECTION_NAME", "shared")
    monkeypatch.setattr(config, "LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME", "checkpoint_writes")

    entry = monitoring_service._check_langgraph_checkpoint_store()

    assert entry.tone == "error"
    assert entry.status == "config error"
    assert "different MongoDB collections" in entry.detail
