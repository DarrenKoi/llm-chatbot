import argparse
import os
import time

from api.utils.logger import log_activity, setup_logging
from api.scheduled_tasks import start_scheduler

IDLE_SECONDS = 60


def run_scheduler_worker() -> None:
    setup_logging()
    start_scheduler()
    log_activity(
        "scheduler_worker_started",
        pid=os.getpid(),
        idle_seconds=IDLE_SECONDS,
    )

    while True:
        log_activity(
            "scheduler_worker_heartbeat",
            pid=os.getpid(),
            idle_seconds=IDLE_SECONDS,
        )
        time.sleep(IDLE_SECONDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the dedicated APScheduler worker.")
    parser.parse_args(argv)
    run_scheduler_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
