import logging
import time
from pathlib import Path

from api import config
from api.utils.scheduler._registry import scheduled_job

logger = logging.getLogger(__name__)

UWSGI_LOG_MAX_AGE_DAYS = 7


def _cleanup_uwsgi_logs() -> None:
    """Delete uWSGI daemonize log files older than 1 week."""
    log_dir = Path(config.LOG_DIR)
    cutoff = time.time() - (UWSGI_LOG_MAX_AGE_DAYS * 86400)

    for log_file in log_dir.glob("uwsgi-*.log"):
        if log_file.stat().st_mtime < cutoff:
            log_file.unlink()
            logger.info("Deleted old uWSGI log: %s", log_file.name)


@scheduled_job(
    id="cleanup_uwsgi_logs",
    trigger="cron",
    hour=3,
    minute=0,
)
def cleanup_uwsgi_logs_job() -> None:
    _cleanup_uwsgi_logs()
