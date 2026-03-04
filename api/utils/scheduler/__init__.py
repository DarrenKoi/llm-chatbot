import logging

from apscheduler.schedulers.background import BackgroundScheduler

from api import config
from api.utils.scheduler._lock import run_locked_job
from api.utils.scheduler._registry import discover_and_register

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

__all__ = ["start_scheduler", "run_locked_job"]


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
            "misfire_grace_time": config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS,
        },
    )
    discover_and_register(_scheduler)
    _scheduler.start()
    logger.info("Background scheduler started")
