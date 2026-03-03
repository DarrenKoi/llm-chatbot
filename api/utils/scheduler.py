import logging
import threading
import time
import uuid
from typing import Callable
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from api import config

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_redis_client = None

UWSGI_LOG_MAX_AGE_DAYS = 7

_LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

_LOCK_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


def _cleanup_uwsgi_logs() -> None:
    """Delete uWSGI daemonize log files older than 1 week."""
    log_dir = Path(config.LOG_DIR)
    cutoff = time.time() - (UWSGI_LOG_MAX_AGE_DAYS * 86400)

    for log_file in log_dir.glob("uwsgi-*.log"):
        if log_file.stat().st_mtime < cutoff:
            log_file.unlink()
            logger.info("Deleted old uWSGI log: %s", log_file.name)


def _normalize_positive(value: int, default: int) -> int:
    return value if value > 0 else default


def _scheduler_lock_key(job_id: str) -> str:
    prefix = config.SCHEDULER_LOCK_PREFIX.strip(":") or "scheduler:lock"
    return f"{prefix}:{job_id}"


def _get_scheduler_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not config.SCHEDULER_REDIS_URL:
        logger.error("SCHEDULER_REDIS_URL is empty. Scheduler jobs will be skipped for safety.")
        return None

    try:
        import redis

        _redis_client = redis.from_url(config.SCHEDULER_REDIS_URL)
        return _redis_client
    except Exception:
        logger.exception("Failed to initialize scheduler Redis client. Scheduler jobs will be skipped.")
        return None


class _RedisDistributedLock:
    def __init__(self, client, key: str, ttl_seconds: int, renew_interval_seconds: int):
        self._client = client
        self._key = key
        self._token = uuid.uuid4().hex
        self._ttl_seconds = _normalize_positive(ttl_seconds, 3600)
        self._renew_interval_seconds = renew_interval_seconds
        self._renew_thread: threading.Thread | None = None
        self._renew_stop_event = threading.Event()

    def acquire(self) -> bool:
        try:
            acquired = self._client.set(self._key, self._token, nx=True, ex=self._ttl_seconds)
        except Exception:
            logger.exception("Failed to acquire scheduler lock: %s", self._key)
            return False

        if not acquired:
            return False

        self._start_renewal()
        return True

    def release(self) -> None:
        self._stop_renewal()
        try:
            self._client.eval(_LOCK_RELEASE_SCRIPT, 1, self._key, self._token)
        except Exception:
            logger.exception("Failed to release scheduler lock: %s", self._key)

    def _start_renewal(self) -> None:
        if self._renew_interval_seconds <= 0:
            return
        if self._renew_interval_seconds >= self._ttl_seconds:
            return

        self._renew_stop_event.clear()
        self._renew_thread = threading.Thread(
            target=self._renew_loop,
            name=f"redis-lock-renew-{self._key}",
            daemon=True,
        )
        self._renew_thread.start()

    def _stop_renewal(self) -> None:
        self._renew_stop_event.set()
        if self._renew_thread is None:
            return
        self._renew_thread.join(timeout=1)
        self._renew_thread = None

    def _renew_loop(self) -> None:
        while not self._renew_stop_event.wait(self._renew_interval_seconds):
            try:
                renewed = self._client.eval(
                    _LOCK_RENEW_SCRIPT,
                    1,
                    self._key,
                    self._token,
                    str(self._ttl_seconds),
                )
                if not renewed:
                    logger.warning("Scheduler lock lost while renewing: %s", self._key)
                    return
            except Exception:
                logger.exception("Failed to renew scheduler lock: %s", self._key)
                return


def _run_locked_job(job_id: str, job_func: Callable[[], None]) -> None:
    redis_client = _get_scheduler_redis_client()
    if redis_client is None:
        logger.error("Skipping scheduler job '%s': Redis lock backend unavailable.", job_id)
        return

    lock = _RedisDistributedLock(
        client=redis_client,
        key=_scheduler_lock_key(job_id),
        ttl_seconds=config.SCHEDULER_LOCK_TTL_SECONDS,
        renew_interval_seconds=config.SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS,
    )
    if not lock.acquire():
        logger.info("Skipping scheduler job '%s': lock already held by another worker.", job_id)
        return

    try:
        job_func()
    finally:
        lock.release()


def _cleanup_uwsgi_logs_job() -> None:
    _run_locked_job("cleanup_uwsgi_logs", _cleanup_uwsgi_logs)


def start_scheduler() -> None:
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(
        daemon=True,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": _normalize_positive(config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS, 1800),
        },
    )
    _scheduler.add_job(
        _cleanup_uwsgi_logs_job,
        trigger="cron",
        hour=3,
        minute=0,
        id="cleanup_uwsgi_logs",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=_normalize_positive(config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS, 1800),
    )
    _scheduler.start()
    logger.info("Background scheduler started")
