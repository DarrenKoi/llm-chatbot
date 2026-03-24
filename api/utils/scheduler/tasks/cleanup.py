import logging
import re
from datetime import date, timedelta
from pathlib import Path

from api import config
from api.utils.scheduler._lock import run_locked_job

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


def _cleanup_uwsgi_logs(*, today: date | None = None) -> None:
    """Delete uWSGI daemonize log files older than 1 week by filename date."""
    log_dir = Path(config.LOG_DIR)
    reference_day = today or date.today()
    cutoff_date = reference_day - timedelta(days=UWSGI_LOG_MAX_AGE_DAYS)

    for pattern in ("uwsgi-*.log", "uwsi-*.log"):
        for log_file in log_dir.glob(pattern):
            log_date = _extract_log_date(log_file)
            if log_date is None:
                continue
            if log_date < cutoff_date:
                log_file.unlink()
                logger.info("Deleted old uWSGI log: %s", log_file.name)


def register(scheduler) -> None:
    def _run() -> None:
        run_locked_job("cleanup_uwsgi_logs", _cleanup_uwsgi_logs)

    scheduler.add_job(
        _run,
        id="cleanup_uwsgi_logs",
        trigger="cron",
        hour=1,
        minute=0,
        replace_existing=True,
    )
