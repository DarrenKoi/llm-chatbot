import logging
import inspect
import threading
from typing import Callable

from api import config

logger = logging.getLogger(__name__)

_redis_client = None


class SchedulerLockLost(RuntimeError):
    """Raised when a scheduled job can no longer prove lock ownership."""


class SchedulerJobLockLease:
    def __init__(self, key: str):
        self._key = key
        self._lost_event = threading.Event()
        self._loss_reason: str | None = None
        self._state_lock = threading.Lock()

    @property
    def key(self) -> str:
        return self._key

    @property
    def loss_reason(self) -> str | None:
        return self._loss_reason

    def is_held(self) -> bool:
        return not self._lost_event.is_set()

    def mark_lost(self, reason: str) -> None:
        with self._state_lock:
            if self._loss_reason is not None:
                return
            self._loss_reason = reason
            self._lost_event.set()

    def ensure_held(self) -> None:
        if self.is_held():
            return

        detail = self._loss_reason or "scheduler lock ownership could not be verified"
        raise SchedulerLockLost(f"Lost scheduler lock '{self._key}': {detail}")


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
        self._ttl_seconds = ttl_seconds
        self._renew_interval_seconds = renew_interval_seconds
        self._renew_thread: threading.Thread | None = None
        self._renew_stop_event = threading.Event()
        self._lease = SchedulerJobLockLease(key)
        self._lock = self._client.lock(
            name=self._key,
            timeout=self._ttl_seconds,
            blocking=False,
            thread_local=False,
        )

    @property
    def lease(self) -> SchedulerJobLockLease:
        return self._lease

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
            if self._lease.is_held():
                logger.exception("Failed to release scheduler lock: %s", self._key)
                return

            logger.warning(
                "Scheduler lock was already lost before release: %s (%s)",
                self._key,
                self._lease.loss_reason,
                exc_info=True,
            )

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
                    self._lease.mark_lost("lock renewal returned false")
                    logger.warning("Scheduler lock lost while renewing: %s", self._key)
                    return
            except Exception:
                self._lease.mark_lost("lock renewal raised an exception")
                logger.exception("Failed to renew scheduler lock: %s", self._key)
                return


def _invoke_job(job_func: Callable, lock_lease: SchedulerJobLockLease) -> None:
    try:
        signature = inspect.signature(job_func)
    except (TypeError, ValueError):
        job_func()
        return

    if "lock_lease" in signature.parameters:
        job_func(lock_lease=lock_lease)
        return

    accepts_positional_arg = any(
        parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in signature.parameters.values()
    )
    accepts_varargs = any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in signature.parameters.values())

    if accepts_positional_arg or accepts_varargs:
        job_func(lock_lease)
        return

    job_func()


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
        lock.lease.ensure_held()
        _invoke_job(job_func, lock.lease)
    except SchedulerLockLost as exc:
        logger.warning("Aborting scheduler job '%s': %s", job_id, exc)
    finally:
        lock.release()
