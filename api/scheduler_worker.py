import argparse
import time

from api import config
from api.utils.logger import log_activity, setup_logging
from api.utils.scheduler import start_scheduler


def run_scheduler_worker() -> None:
    setup_logging()
    start_scheduler()
    log_activity(
        "scheduler_worker_started",
        idle_seconds=max(1, config.SCHEDULER_WORKER_IDLE_SECONDS),
        member_refresh_enabled=config.MEMBER_REFRESH_ENABLED,
        member_refresh_batch_size=config.MEMBER_REFRESH_BATCH_SIZE,
        member_refresh_interval_minutes=config.MEMBER_REFRESH_INTERVAL_MINUTES,
    )

    while True:
        time.sleep(max(1, config.SCHEDULER_WORKER_IDLE_SECONDS))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the dedicated APScheduler worker.")
    parser.parse_args(argv)
    run_scheduler_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
