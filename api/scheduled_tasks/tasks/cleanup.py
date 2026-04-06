import logging
import re
from datetime import date, timedelta
from pathlib import Path

from api import config
from api.file_delivery import delete_file, get_expired_file_ids
from api.scheduled_tasks._lock import SchedulerJobLockLease, run_locked_job
from api.scheduled_tasks._registry import _RUNTIME_META_ATTR

logger = logging.getLogger(__name__)

UWSGI_LOG_MAX_AGE_DAYS = 7
_UWSGI_LOG_NAME_PATTERN = re.compile(r"^uws(?:g)?i-(\d{4}-\d{2}-\d{2})\.log$")


def _extract_log_date(log_file: Path) -> date | None:
    match = _UWSGI_LOG_NAME_PATTERN.match(log_file.name)
    if match is None:
        return None

    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _cleanup_uwsgi_logs(lock_lease: SchedulerJobLockLease | None = None, *, today: date | None = None) -> None:
    """Delete uWSGI daemonize log files older than 1 week by filename date."""
    log_dir = Path(config.LOG_DIR)
    reference_day = today or date.today()
    cutoff_date = reference_day - timedelta(days=UWSGI_LOG_MAX_AGE_DAYS)

    for pattern in ("uwsgi-*.log", "uwsi-*.log"):
        if lock_lease is not None:
            lock_lease.ensure_held()
        for log_file in log_dir.glob(pattern):
            if lock_lease is not None:
                lock_lease.ensure_held()
            log_date = _extract_log_date(log_file)
            if log_date is None:
                continue
            if log_date < cutoff_date:
                log_file.unlink()
                logger.info("Deleted old uWSGI log: %s", log_file.name)


def _cleanup_expired_file_delivery_files(lock_lease: SchedulerJobLockLease | None = None) -> None:
    if lock_lease is not None:
        lock_lease.ensure_held()
    expired_file_ids = get_expired_file_ids()
    deleted_count = 0

    for file_id in expired_file_ids:
        if lock_lease is not None:
            lock_lease.ensure_held()
        if delete_file(file_id):
            deleted_count += 1

    if deleted_count > 0:
        logger.info("Deleted %s expired file delivery item(s).", deleted_count)


def register(scheduler) -> None:
    def _run_uwsgi_cleanup() -> None:
        run_locked_job("cleanup_uwsgi_logs", _cleanup_uwsgi_logs)

    setattr(
        _run_uwsgi_cleanup,
        _RUNTIME_META_ATTR,
        {
            "lock_id": "cleanup_uwsgi_logs",
            "source": f"{_cleanup_uwsgi_logs.__module__}.{_cleanup_uwsgi_logs.__qualname__}",
            "use_distributed_lock": True,
        },
    )
    scheduler.add_job(
        _run_uwsgi_cleanup,
        id="cleanup_uwsgi_logs",
        trigger="cron",
        hour=1,
        minute=0,
        replace_existing=True,
    )

    def _run_file_delivery_cleanup() -> None:
        run_locked_job("cleanup_file_delivery", _cleanup_expired_file_delivery_files)

    setattr(
        _run_file_delivery_cleanup,
        _RUNTIME_META_ATTR,
        {
            "lock_id": "cleanup_file_delivery",
            "source": (
                f"{_cleanup_expired_file_delivery_files.__module__}.{_cleanup_expired_file_delivery_files.__qualname__}"
            ),
            "use_distributed_lock": True,
        },
    )
    scheduler.add_job(
        _run_file_delivery_cleanup,
        id="cleanup_file_delivery",
        trigger="cron",
        hour=2,
        minute=0,
        replace_existing=True,
    )
