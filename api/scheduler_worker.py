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
        hynix_member_info_enabled=config.HYNIX_MEMBER_INFO_ENABLED,
        hynix_member_info_batch_size=config.HYNIX_MEMBER_INFO_BATCH_SIZE,
        hynix_member_info_interval_minutes=config.HYNIX_MEMBER_INFO_INTERVAL_MINUTES,
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
