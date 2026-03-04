from unittest.mock import MagicMock

from api import config
from api.utils.scheduler import _lock as lock_mod
from api.utils.scheduler import _registry as registry_mod
import api.utils.scheduler as scheduler_pkg


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def eval(self, script, numkeys, key, *args):
        token = args[0]
        current = self.store.get(key)

        if "del" in script:
            if current == token:
                del self.store[key]
                return 1
            return 0

        if "expire" in script:
            if current == token:
                return 1
            return 0

        return 0


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
    monkeypatch.setattr(scheduler_pkg, "BackgroundScheduler", _fake_scheduler_factory)
    monkeypatch.setattr(scheduler_pkg, "_scheduler", None)

    scheduler_pkg.start_scheduler()
    scheduler_pkg.start_scheduler()

    assert mock_scheduler.add_job.call_count == 1
    kwargs = mock_scheduler.add_job.call_args.kwargs
    assert kwargs["id"] == "cleanup_uwsgi_logs"
    assert kwargs["max_instances"] == 1
    assert kwargs["coalesce"] is True
    assert kwargs["misfire_grace_time"] == 900
    mock_scheduler.start.assert_called_once()
