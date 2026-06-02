import argparse
import os
import time
from typing import Any

from api import config
from api.cube.queue import (
    CubeQueueError,
    acknowledge_queued_message,
    dequeue_queued_message,
    is_message_processed,
    mark_message_processed,
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


def _is_stale_message(queued_message: Any) -> bool:
    """TTL을 초과했거나 타임스탬프가 없는(구버전) 메시지를 폐기 대상으로 판단한다.

    enqueued_at이 없으면 나이를 알 수 없으므로 stale로 간주한다. 이는 워커/LLM 재기동 시
    타임스탬프 이전에 쌓여 있던 백로그를 1회 비워내기 위한 의도된 동작이다.
    TTL이 0 이하이면 검사를 비활성화한다.
    """
    ttl = config.CUBE_QUEUE_MESSAGE_TTL_SECONDS
    if ttl <= 0:
        return False
    if queued_message.enqueued_at is None:
        return True
    return (time.time() - queued_message.enqueued_at) > ttl


def _mark_processed_best_effort(incoming: Any) -> None:
    """처리 완료 마커를 기록한다. 마커 기록 실패가 정상 처리를 되돌리면 안 되므로 best-effort로 둔다.

    기록에 실패하면 이 메시지에 한해 멱등성 보호가 사라질 뿐(= 기존 동작), 사용자 응답에는 영향이 없다.
    """
    try:
        mark_message_processed(incoming)
    except CubeQueueError as exc:
        log_activity(
            "cube_worker_mark_processed_failed",
            level="WARNING",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            error=str(exc),
        )


def process_next_queued_message(*, timeout_seconds: int | None = None) -> bool:
    queued_message = dequeue_queued_message(timeout_seconds=timeout_seconds)
    if queued_message is None:
        return False

    incoming = queued_message.incoming

    if is_message_processed(incoming):
        # 이미 응답을 보낸 메시지가 재시작 복구(recover)로 되돌아온 경우. 재처리 없이 ack만 한다.
        acknowledge_queued_message(queued_message)
        log_activity(
            "cube_worker_message_duplicate_skipped",
            level="WARNING",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            queue_attempt=queued_message.attempt,
        )
        return True

    if _is_stale_message(queued_message):
        acknowledge_queued_message(queued_message)
        enqueued_at = queued_message.enqueued_at
        age_seconds = round(time.time() - enqueued_at, 1) if enqueued_at is not None else None
        log_activity(
            "cube_worker_message_stale",
            level="WARNING",
            user_id=incoming.user_id,
            user_name=incoming.user_name,
            channel_id=incoming.channel_id,
            message_id=incoming.message_id,
            queue_attempt=queued_message.attempt,
            age_seconds=age_seconds,
            ttl_seconds=config.CUBE_QUEUE_MESSAGE_TTL_SECONDS,
        )
        return True

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

    _mark_processed_best_effort(incoming)
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
