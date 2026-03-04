"""
Scheduler task registration examples.

This file is NOT auto-discovered (prefixed with underscore).
Copy any example below into a new task file to use it.

Available triggers:
  - cron     : Unix-like cron schedule (fixed times)
  - interval : Run every N seconds/minutes/hours
  - date     : Run once at a specific datetime


== Cron examples ==

# Every day at 03:00
trigger="cron", hour=3, minute=0

# Every Monday at 06:30
trigger="cron", day_of_week="mon", hour=6, minute=30

# Every Sunday at 00:00 (once a week)
trigger="cron", day_of_week="sun", hour=0, minute=0

# First day of every month at 09:00
trigger="cron", day=1, hour=9, minute=0

# Every weekday (Mon-Fri) at 08:00
trigger="cron", day_of_week="mon-fri", hour=8, minute=0

# Every 6 hours (00:00, 06:00, 12:00, 18:00)
trigger="cron", hour="*/6", minute=0

# Every 30 minutes
trigger="cron", minute="*/30"


== Interval examples ==

# Every 5 minutes
trigger="interval", minutes=5

# Every 1 hour
trigger="interval", hours=1

# Every 30 seconds
trigger="interval", seconds=30

# Every 2 hours, starting 10 minutes after scheduler launch
from datetime import datetime, timedelta
trigger="interval", hours=2, start_date=datetime.now() + timedelta(minutes=10)


== Date example (run once) ==

# Run once at a specific time
from datetime import datetime
trigger="date", run_date=datetime(2026, 4, 1, 9, 0, 0)
"""

# ---------------------------------------------------------------------------
# Example 1: Daily task (cron, once a day at 03:00)
# ---------------------------------------------------------------------------
#
# import logging
#
# from api.utils.scheduler._lock import run_locked_job
#
# logger = logging.getLogger(__name__)
#
#
# def _daily_report() -> None:
#     logger.info("Generating daily report...")
#
#
# def register(scheduler) -> None:
#     scheduler.add_job(
#         lambda: run_locked_job("daily_report", _daily_report),
#         trigger="cron",
#         hour=3,
#         minute=0,
#         id="daily_report",
#         replace_existing=True,
#         max_instances=1,
#         coalesce=True,
#     )


# ---------------------------------------------------------------------------
# Example 2: Weekly task (cron, every Sunday at midnight)
# ---------------------------------------------------------------------------
#
# import logging
#
# from api.utils.scheduler._lock import run_locked_job
#
# logger = logging.getLogger(__name__)
#
#
# def _weekly_cleanup() -> None:
#     logger.info("Running weekly cleanup...")
#
#
# def register(scheduler) -> None:
#     scheduler.add_job(
#         lambda: run_locked_job("weekly_cleanup", _weekly_cleanup),
#         trigger="cron",
#         day_of_week="sun",
#         hour=0,
#         minute=0,
#         id="weekly_cleanup",
#         replace_existing=True,
#         max_instances=1,
#         coalesce=True,
#     )


# ---------------------------------------------------------------------------
# Example 3: Interval task (every 10 minutes)
# ---------------------------------------------------------------------------
#
# import logging
#
# from api.utils.scheduler._lock import run_locked_job
#
# logger = logging.getLogger(__name__)
#
#
# def _health_check() -> None:
#     logger.info("Running periodic health check...")
#
#
# def register(scheduler) -> None:
#     scheduler.add_job(
#         lambda: run_locked_job("health_check", _health_check),
#         trigger="interval",
#         minutes=10,
#         id="health_check",
#         replace_existing=True,
#         max_instances=1,
#         coalesce=True,
#     )


# ---------------------------------------------------------------------------
# Example 4: Lightweight interval task WITHOUT distributed lock
#            (safe to run on every worker, e.g. in-memory cache refresh)
# ---------------------------------------------------------------------------
#
# import logging
#
# logger = logging.getLogger(__name__)
#
#
# def _refresh_cache() -> None:
#     logger.info("Refreshing local cache...")
#
#
# def register(scheduler) -> None:
#     scheduler.add_job(
#         _refresh_cache,
#         trigger="interval",
#         minutes=5,
#         id="refresh_cache",
#         replace_existing=True,
#         max_instances=1,
#         coalesce=True,
#     )
