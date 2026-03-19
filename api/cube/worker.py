from __future__ import annotations

import argparse
import time

from api import config
from api.cube.queue import (
    CubeQueueError,
    acknowledge_queued_message,
    dequeue_queued_message,
    recover_processing_messages,
    requeue_queued_message,
)
from api.cube.service import process_queued_message
from api.utils.logger import log_activity, setup_logging


def process_next_queued_message(*, timeout_seconds: int | None = None) -> bool:
    queued_message = dequeue_queued_message(timeout_seconds=timeout_seconds)
    if queued_message is None:
        return False

    incoming = queued_message.incoming
    try:
        process_queued_message(queued_message)
    except Exception as exc:
        next_attempt = queued_message.attempt + 1
        max_retries = max(1, config.CUBE_QUEUE_MAX_RETRIES)
        if next_attempt < max_retries:
            requeue_queued_message(queued_message, next_attempt=next_attempt)
            log_activity(
                "cube_worker_message_requeued",
                level="WARNING",
                user_id=incoming.user_id,
                user_name=incoming.user_name,
                channel_id=incoming.channel_id,
                message_id=incoming.message_id,
                queue_attempt=queued_message.attempt,
                next_attempt=next_attempt,
                max_retries=max_retries,
                error=str(exc),
            )
        else:
            acknowledge_queued_message(queued_message)
            log_activity(
                "cube_worker_message_failed",
                level="ERROR",
                user_id=incoming.user_id,
                user_name=incoming.user_name,
                channel_id=incoming.channel_id,
                message_id=incoming.message_id,
                queue_attempt=queued_message.attempt,
                attempts=next_attempt,
                max_retries=max_retries,
                error=str(exc),
            )
        return True

    acknowledge_queued_message(queued_message)
    log_activity(
        "cube_worker_message_processed",
        user_id=incoming.user_id,
        user_name=incoming.user_name,
        channel_id=incoming.channel_id,
        message_id=incoming.message_id,
        queue_attempt=queued_message.attempt,
    )
    return True


def run_worker(*, once: bool = False) -> None:
    setup_logging()
    recovered_count = recover_processing_messages()
    log_activity(
        "cube_worker_started",
        recovered_count=recovered_count,
        block_timeout_seconds=config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS,
        max_retries=max(1, config.CUBE_QUEUE_MAX_RETRIES),
    )

    while True:
        try:
            processed = process_next_queued_message(
                timeout_seconds=0 if once else config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS
            )
        except CubeQueueError as exc:
            log_activity("cube_worker_queue_failed", level="ERROR", error=str(exc))
            if once:
                raise
            time.sleep(max(1, config.CUBE_WORKER_RETRY_DELAY_SECONDS))
            continue

        if once:
            return

        if not processed:
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Redis-backed Cube worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued message and exit.")
    args = parser.parse_args(argv)
    run_worker(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
