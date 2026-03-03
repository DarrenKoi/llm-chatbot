import logging
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from api import config

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

UWSGI_LOG_MAX_AGE_DAYS = 7


def _cleanup_uwsgi_logs() -> None:
    """Delete uWSGI daemonize log files older than 1 week."""
    log_dir = Path(config.LOG_DIR)
    cutoff = time.time() - (UWSGI_LOG_MAX_AGE_DAYS * 86400)

    for log_file in log_dir.glob("uwsgi-*.log"):
        if log_file.stat().st_mtime < cutoff:
            log_file.unlink()
            logger.info("Deleted old uWSGI log: %s", log_file.name)


def start_scheduler() -> None:
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _cleanup_uwsgi_logs,
        trigger="cron",
        hour=3,
        minute=0,
        id="cleanup_uwsgi_logs",
    )
    _scheduler.start()
    logger.info("Background scheduler started")
