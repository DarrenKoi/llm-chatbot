import argparse
import os
import time

from api.scheduled_tasks import start_scheduler
from api.utils.logger import log_activity, setup_logging

IDLE_SECONDS = 60


def run_scheduler_worker() -> None:
    """APScheduler를 시작하고, IDLE_SECONDS 주기로 heartbeat를 activity log에 기록한다.

    모니터링 대시보드는 이 heartbeat를 통해 스케줄러 워커가 살아있는지 확인한다.
    """
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
    """스케줄러 워커의 CLI 진입점. `python -m api.scheduler_worker` 또는 uWSGI attach-daemon으로 실행한다."""
    parser = argparse.ArgumentParser(description="Run the dedicated APScheduler worker.")
    parser.parse_args(argv)
    run_scheduler_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
