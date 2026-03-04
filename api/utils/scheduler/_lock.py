import logging
import threading
from typing import Callable

from api import config

logger = logging.getLogger(__name__)

_redis_client = None


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
        self._ttl_seconds = _normalize_positive(ttl_seconds, 3600)
        self._renew_interval_seconds = renew_interval_seconds
        self._renew_thread: threading.Thread | None = None
        self._renew_stop_event = threading.Event()
        self._lock = self._client.lock(
            name=self._key,
            timeout=self._ttl_seconds,
            blocking=False,
            thread_local=False,
        )

    def acquire(self) -> bool:
        try:
            acquired = self._lock.acquire(blocking=False)
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
            self._lock.release()
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
                try:
                    renewed = self._lock.extend(self._ttl_seconds, replace_ttl=True)
                except TypeError:
                    renewed = self._lock.extend(self._ttl_seconds)
                if not renewed:
                    logger.warning("Scheduler lock lost while renewing: %s", self._key)
                    return
            except Exception:
                logger.exception("Failed to renew scheduler lock: %s", self._key)
                return


def run_locked_job(job_id: str, job_func: Callable[[], None]) -> None:
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
