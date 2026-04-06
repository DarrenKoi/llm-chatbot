import argparse
import logging
import os
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

_HEARTBEAT_INTERVAL_SECONDS = 60
logger = logging.getLogger(__name__)


def process_next_queued_message(*, timeout_seconds: int | None = None) -> bool:
    queued_message = dequeue_queued_message(timeout_seconds=timeout_seconds)
    if queued_message is None:
        return False

    incoming = queued_message.incoming
    logger.info(
        "Cube worker processing started: user_id=%s message_id=%s attempt=%d timeout_seconds=%s",
        incoming.user_id,
        incoming.message_id,
        queued_message.attempt,
        timeout_seconds,
    )
    try:
        process_queued_message(queued_message)
    except Exception as exc:
        next_attempt = queued_message.attempt + 1
        max_retries = max(1, config.CUBE_QUEUE_MAX_RETRIES)
        if next_attempt < max_retries:
            requeue_queued_message(queued_message, next_attempt=next_attempt)
            logger.warning(
                "Cube worker requeued message: user_id=%s message_id=%s attempt=%d next_attempt=%d max_retries=%d",
                incoming.user_id,
                incoming.message_id,
                queued_message.attempt,
                next_attempt,
                max_retries,
            )
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
            logger.error(
                "Cube worker failed message permanently: user_id=%s message_id=%s attempt=%d max_retries=%d",
                incoming.user_id,
                incoming.message_id,
                queued_message.attempt,
                max_retries,
            )
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
    logger.info(
        "Cube worker processing completed: user_id=%s message_id=%s attempt=%d",
        incoming.user_id,
        incoming.message_id,
        queued_message.attempt,
    )
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
        pid=os.getpid(),
        recovered_count=recovered_count,
        block_timeout_seconds=config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS,
        max_retries=max(1, config.CUBE_QUEUE_MAX_RETRIES),
    )
    last_heartbeat_at: float | None = None

    while True:
        if not once:
            last_heartbeat_at = _emit_worker_heartbeat(last_heartbeat_at)
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


def _emit_worker_heartbeat(last_heartbeat_at: float | None) -> float:
    now = time.monotonic()
    if last_heartbeat_at is not None and (now - last_heartbeat_at) < _HEARTBEAT_INTERVAL_SECONDS:
        return last_heartbeat_at

    log_activity(
        "cube_worker_heartbeat",
        pid=os.getpid(),
        queue_name=config.CUBE_QUEUE_NAME,
        block_timeout_seconds=config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS,
    )
    return now


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Redis-backed Cube worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued message and exit.")
    args = parser.parse_args(argv)
    run_worker(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
