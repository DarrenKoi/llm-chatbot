import time
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import api.scheduled_tasks as scheduler_pkg
from api import config
from api.scheduled_tasks import _lock as lock_mod
from api.scheduled_tasks import _registry as registry_mod


class _FakeRedis:
    def __init__(self, *, extend_results: list[bool | Exception] | None = None):
        self.store: dict[str, str] = {}
        self.extend_results = list(extend_results or [])

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def lock(self, name, timeout=None, blocking=True, thread_local=True):
        return _FakeRedisLock(self, name)


class _FakeRedisLock:
    def __init__(self, client: _FakeRedis, key: str):
        self._client = client
        self._key = key
        self._token: str | None = None

    def acquire(self, blocking=False):
        if self._key in self._client.store:
            return False
        self._token = uuid.uuid4().hex
        self._client.store[self._key] = self._token
        return True

    def release(self):
        current = self._client.store.get(self._key)
        if self._token is None or current != self._token:
            raise RuntimeError("lock not owned")
        del self._client.store[self._key]

    def extend(self, additional_time, replace_ttl=False):
        current = self._client.store.get(self._key)
        if self._token is None or current != self._token:
            return False
        if self._client.extend_results:
            result = self._client.extend_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return True


def test_run_locked_job_executes_and_releases(monkeypatch):
    fake_redis = _FakeRedis()
    called = []

    monkeypatch.setattr(config, "SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
    monkeypatch.setattr(config, "SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(lock_mod, "_get_scheduler_redis_client", lambda: fake_redis)

    lock_mod.run_locked_job("job_a", lambda: called.append("run"))

    assert called == ["run"]
    assert fake_redis.get("scheduler:sknn_v3:job_a") is None


def test_run_locked_job_skips_when_lock_already_held(monkeypatch):
    fake_redis = _FakeRedis()
    fake_redis.set("scheduler:sknn_v3:job_b", "other-token", nx=True, ex=3600)
    called = []

    monkeypatch.setattr(config, "SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
    monkeypatch.setattr(config, "SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(lock_mod, "_get_scheduler_redis_client", lambda: fake_redis)

    lock_mod.run_locked_job("job_b", lambda: called.append("run"))

    assert called == []


def test_run_locked_job_skips_without_redis(monkeypatch):
    called = []
    monkeypatch.setattr(lock_mod, "_get_scheduler_redis_client", lambda: None)

    lock_mod.run_locked_job("job_c", lambda: called.append("run"))

    assert called == []


def test_run_locked_job_aborts_when_lock_is_lost(monkeypatch):
    fake_redis = _FakeRedis(extend_results=[True, False])
    steps: list[str] = []

    monkeypatch.setattr(config, "SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")
    monkeypatch.setattr(config, "SCHEDULER_LOCK_TTL_SECONDS", 60)
    monkeypatch.setattr(config, "SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(lock_mod, "_get_scheduler_redis_client", lambda: fake_redis)

    def _job(lock_lease) -> None:
        for _ in range(100):
            time.sleep(0.01)
            lock_lease.ensure_held()
            steps.append("tick")

    lock_mod.run_locked_job("job_loss", _job)

    assert 0 < len(steps) < 100
    assert fake_redis.get("scheduler:sknn_v3:job_loss") is None


def test_start_scheduler_uses_strict_job_defaults(monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()

    def _fake_scheduler_factory(*, daemon, job_defaults):
        assert daemon is True
        assert job_defaults["coalesce"] is True
        assert job_defaults["max_instances"] == 1
        assert job_defaults["misfire_grace_time"] == 900
        return mock_scheduler

    monkeypatch.setattr(config, "SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 900)
    monkeypatch.setattr(config, "FILE_DELIVERY_CLEANUP_HOUR", 1)
    monkeypatch.setattr(config, "FILE_DELIVERY_CLEANUP_MINUTE", 0)
    monkeypatch.setattr(scheduler_pkg, "BackgroundScheduler", _fake_scheduler_factory)
    monkeypatch.setattr(scheduler_pkg, "_scheduler", None)

    scheduler_pkg.start_scheduler()
    scheduler_pkg.start_scheduler()

    assert mock_scheduler.add_job.call_count == 2

    registered_jobs = [call.kwargs for call in mock_scheduler.add_job.call_args_list]
    registered_job_ids = {job["id"] for job in registered_jobs}
    assert registered_job_ids == {"cleanup_uwsgi_logs", "cleanup_file_delivery"}

    jobs_by_id = {job["id"]: job for job in registered_jobs}
    assert jobs_by_id["cleanup_uwsgi_logs"]["hour"] == 1
    assert jobs_by_id["cleanup_uwsgi_logs"]["minute"] == 0
    assert jobs_by_id["cleanup_file_delivery"]["hour"] == 1
    assert jobs_by_id["cleanup_file_delivery"]["minute"] == 0

    for kwargs in registered_jobs:
        assert kwargs["trigger"] == "cron"
        assert "max_instances" not in kwargs, "per-job max_instances should come from job_defaults"
        assert "coalesce" not in kwargs, "per-job coalesce should come from job_defaults"
        assert "misfire_grace_time" not in kwargs, "per-job misfire_grace_time should come from job_defaults"

    mock_scheduler.start.assert_called_once()


def test_start_scheduler_falls_back_when_file_cleanup_schedule_is_invalid(monkeypatch):
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.start = MagicMock()

    monkeypatch.setattr(config, "SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 900)
    monkeypatch.setattr(config, "FILE_DELIVERY_CLEANUP_HOUR", 99)
    monkeypatch.setattr(config, "FILE_DELIVERY_CLEANUP_MINUTE", -5)
    monkeypatch.setattr(scheduler_pkg, "BackgroundScheduler", lambda **_kwargs: mock_scheduler)
    monkeypatch.setattr(scheduler_pkg, "_scheduler", None)

    scheduler_pkg.start_scheduler()

    registered_jobs = {call.kwargs["id"]: call.kwargs for call in mock_scheduler.add_job.call_args_list}
    assert registered_jobs["cleanup_file_delivery"]["hour"] == 1
    assert registered_jobs["cleanup_file_delivery"]["minute"] == 0
    mock_scheduler.start.assert_called_once()


def test_discover_and_register_supports_scheduled_job_decorator(monkeypatch):
    mock_scheduler = MagicMock()

    @registry_mod.scheduled_job(
        id="decorator_job",
        trigger="interval",
        minutes=5,
        use_distributed_lock=False,
    )
    def _job() -> None:
        return

    fake_module = SimpleNamespace(
        __name__="api.scheduled_tasks.tasks.fake",
        decorator_job=_job,
    )
    fake_module_info = SimpleNamespace(name="api.scheduled_tasks.tasks.fake")

    monkeypatch.setattr(registry_mod.pkgutil, "iter_modules", lambda *_args, **_kwargs: [fake_module_info])
    monkeypatch.setattr(registry_mod.importlib, "import_module", lambda _name: fake_module)
    monkeypatch.setattr(registry_mod, "_TASK_PACKAGES", [])

    registry_mod.discover_and_register(mock_scheduler)

    assert mock_scheduler.add_job.call_count == 1
    args = mock_scheduler.add_job.call_args.args
    kwargs = mock_scheduler.add_job.call_args.kwargs
    assert args[0] is _job
    assert kwargs["id"] == "decorator_job"
    assert kwargs["trigger"] == "interval"
    assert kwargs["minutes"] == 5
    assert "max_instances" not in kwargs, "per-job max_instances should come from job_defaults"
    assert "coalesce" not in kwargs, "per-job coalesce should come from job_defaults"
    assert "misfire_grace_time" not in kwargs, "per-job misfire_grace_time should come from job_defaults"
