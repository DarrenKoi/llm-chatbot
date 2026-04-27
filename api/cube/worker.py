import argparse
import os
import time
from typing import Any

from api import config
from api.cube.queue import (
    CubeQueueError,
    acknowledge_queued_message,
    dequeue_queued_message,
    recover_processing_messages,
    requeue_queued_message,
)
from api.cube.service import process_queued_message
from api.logging_service import log_activity, setup_logging

_HEARTBEAT_INTERVAL_SECONDS = 60


def check_worker_connections() -> int:
    """Worker 프로세스 기준 MongoDB와 LangGraph 체크포인터 연결 상태를 출력한다."""

    from api.mongo import get_mongo_client
    from api.workflows.langgraph_checkpoint import get_checkpointer, get_mongo_storage_collections

    collections = get_mongo_storage_collections()
    print("worker connection check")
    print(f"pid={os.getpid()}")
    print(f"AFM_MONGO_URI_set={bool(config.AFM_MONGO_URI)}")
    print(f"AFM_DB_NAME={config.AFM_DB_NAME}")
    print(f"conversation_collection={collections.conversation_history}")
    print(f"checkpoint_collection={collections.checkpoint}")
    print(f"checkpoint_writes_collection={collections.checkpoint_writes}")
    print(f"CHECKPOINT_TTL_SECONDS={config.CHECKPOINT_TTL_SECONDS}")

    mongo_ok = False
    if config.AFM_MONGO_URI:
        try:
            client = get_mongo_client()
            client.admin.command("ping")
            db = client[config.AFM_DB_NAME]
            print("mongo_ping=ok")
            print(f"conversation_count={db[collections.conversation_history].count_documents({})}")
            mongo_ok = True
        except Exception as exc:
            print(f"mongo_ping=failed: {exc}")
    else:
        print("mongo_ping=skipped: AFM_MONGO_URI is empty")

    try:
        checkpointer = get_checkpointer()
    except Exception as exc:
        print(f"checkpointer=failed: {exc}")
        return 1

    print(f"checkpointer_type={type(checkpointer).__module__}.{type(checkpointer).__name__}")
    checkpoint_collection = getattr(checkpointer, "checkpoint_collection", None)
    writes_collection = getattr(checkpointer, "writes_collection", None)
    if checkpoint_collection is None or writes_collection is None:
        print("checkpointer_backend=memory")
        print("checkpoint_persistence=disabled")
        return 1

    print("checkpointer_backend=mongodb")
    print(f"checkpoint_full_name={checkpoint_collection.full_name}")
    print(f"writes_full_name={writes_collection.full_name}")
    print(f"checkpointer_ttl={getattr(checkpointer, 'ttl', None)}")
    print(f"checkpoint_count={checkpoint_collection.count_documents({})}")
    print(f"writes_count={writes_collection.count_documents({})}")

    latest_checkpoint = _latest_checkpoint_summary(checkpoint_collection)
    if latest_checkpoint:
        print("latest_checkpoint=" + latest_checkpoint)
    else:
        print("latest_checkpoint=None")

    return 0 if mongo_ok else 1


def _latest_checkpoint_summary(collection: Any) -> str:
    latest = collection.find_one(
        {},
        {"checkpoint": 0, "metadata": 0},
        sort=[("checkpoint_id", -1)],
    )
    if not latest:
        return ""
    return (
        f"thread_id={latest.get('thread_id')} "
        f"checkpoint_ns={latest.get('checkpoint_ns')} "
        f"checkpoint_id={latest.get('checkpoint_id')}"
    )


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
    parser.add_argument(
        "--check-connections",
        action="store_true",
        help="Check MongoDB and LangGraph checkpointer from the worker runtime, then exit.",
    )
    args = parser.parse_args(argv)
    if args.check_connections:
        return check_worker_connections()
    run_worker(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
