import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from api import config
from api.utils.logger.paths import get_theme_log_dir
from api.workflows.langgraph_checkpoint import validate_mongo_storage_config

MonitorTone = Literal["ok", "warning", "error", "disabled"]
_ACTIVITY_TAIL_LINES = 400
_MIN_DAEMON_STALE_SECONDS = 180


@dataclass(slots=True)
class MonitorEntry:
    name: str
    backend: str
    tone: MonitorTone
    status: str
    target: str
    detail: str


def get_monitoring_snapshot() -> dict[str, object]:
    entries = [
        _check_langgraph_checkpoint_store(),
        _check_mongo_conversation_store(),
        _check_cube_queue(),
        _check_cube_worker_daemon(),
        _check_scheduler_lock(),
        _check_scheduler_worker_daemon(),
        _check_file_delivery_metadata(),
    ]
    return {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entries": [asdict(entry) for entry in entries],
        "summary": {
            "healthy": sum(entry.tone == "ok" for entry in entries),
            "warnings": sum(entry.tone == "warning" for entry in entries),
            "errors": sum(entry.tone == "error" for entry in entries),
            "disabled": sum(entry.tone == "disabled" for entry in entries),
        },
    }


def _check_mongo_conversation_store() -> MonitorEntry:
    backend_name = (config.CONVERSATION_BACKEND or "auto").strip().lower()
    if backend_name == "local":
        target = str(config.CONVERSATION_LOCAL_DIR)
        return MonitorEntry(
            name="Conversation Store",
            backend="Local File",
            tone="ok" if config.CONVERSATION_LOCAL_DIR.exists() else "warning",
            status="connected" if config.CONVERSATION_LOCAL_DIR.exists() else "ready",
            target=target,
            detail="대화 이력은 로컬 파일 백엔드에 저장됩니다.",
        )
    if backend_name == "memory":
        return MonitorEntry(
            name="Conversation Store",
            backend="Memory",
            tone="warning",
            status="fallback",
            target="process memory",
            detail="대화 이력은 프로세스 메모리 백엔드로 동작합니다.",
        )

    try:
        collections = validate_mongo_storage_config()
    except ValueError as exc:
        return MonitorEntry(
            name="Conversation Store",
            backend="MongoDB",
            tone="error",
            status="config error",
            target=config.CONVERSATION_COLLECTION_NAME,
            detail=str(exc),
        )

    if not config.AFM_MONGO_URI:
        return MonitorEntry(
            name="Conversation Store",
            backend="MongoDB",
            tone="warning",
            status="fallback",
            target=collections.conversation_history,
            detail="AFM_MONGO_URI가 비어 있어 현재 대화 이력은 메모리 백엔드로 동작합니다.",
        )

    try:
        from pymongo import MongoClient

        client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
        try:
            client.admin.command("ping")
        finally:
            client.close()
    except Exception as exc:
        return MonitorEntry(
            name="Conversation Store",
            backend="MongoDB",
            tone="error",
            status="failed",
            target=f"{_mask_url(config.AFM_MONGO_URI)} / {collections.conversation_history}",
            detail=f"MongoDB ping 실패: {exc}. 현재 설정에서는 대화 이력을 메모리로 fallback 하지 않습니다.",
        )

    return MonitorEntry(
        name="Conversation Store",
        backend="MongoDB",
        tone="ok",
        status="connected",
        target=f"{_mask_url(config.AFM_MONGO_URI)} / {collections.conversation_history}",
        detail=f"DB `{config.AFM_DB_NAME}` 의 대화 이력 컬렉션에 정상 연결되었습니다.",
    )


def _check_langgraph_checkpoint_store() -> MonitorEntry:
    try:
        collections = validate_mongo_storage_config()
    except ValueError as exc:
        return MonitorEntry(
            name="LangGraph Checkpointer",
            backend="MongoDB",
            tone="error",
            status="config error",
            target=(
                f"{config.LANGGRAPH_CHECKPOINT_COLLECTION_NAME} / {config.LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME}"
            ),
            detail=str(exc),
        )

    checkpoint_target = f"{collections.checkpoint} / {collections.checkpoint_writes}"
    ttl_seconds = config.CHECKPOINT_TTL_SECONDS if config.CHECKPOINT_TTL_SECONDS > 0 else None

    if not config.AFM_MONGO_URI:
        return MonitorEntry(
            name="LangGraph Checkpointer",
            backend="MongoDB",
            tone="warning",
            status="fallback",
            target=checkpoint_target,
            detail="AFM_MONGO_URI가 비어 있어 LangGraph 체크포인터는 메모리 백엔드로 동작합니다.",
        )

    try:
        from pymongo import MongoClient

        client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
        try:
            client.admin.command("ping")
        finally:
            client.close()
    except Exception as exc:
        return MonitorEntry(
            name="LangGraph Checkpointer",
            backend="MongoDB",
            tone="error",
            status="failed",
            target=f"{_mask_url(config.AFM_MONGO_URI)} / {checkpoint_target}",
            detail=f"MongoDB ping 실패: {exc}. LangGraph 체크포인터를 영속적으로 사용할 수 없습니다.",
        )

    ttl_detail = f"TTL={ttl_seconds}초" if ttl_seconds is not None else "TTL 비활성"
    return MonitorEntry(
        name="LangGraph Checkpointer",
        backend="MongoDB",
        tone="ok",
        status="connected",
        target=f"{_mask_url(config.AFM_MONGO_URI)} / {checkpoint_target}",
        detail=f"DB `{config.AFM_DB_NAME}` 의 체크포인터 컬렉션에 정상 연결되었습니다. {ttl_detail}.",
    )


def _check_cube_queue() -> MonitorEntry:
    target = f"{config.CUBE_QUEUE_NAME} / {config.CUBE_QUEUE_PROCESSING_NAME}"
    if not config.CUBE_QUEUE_REDIS_URL:
        return MonitorEntry(
            name="Cube Queue",
            backend="Redis",
            tone="error",
            status="not configured",
            target=target,
            detail="REDIS_URL 이 없어 Cube Queue 를 사용할 수 없습니다.",
        )

    client = None
    probe_suffix = uuid4().hex
    ready_key = f"{config.CUBE_QUEUE_NAME}:monitor:{probe_suffix}"
    processing_key = f"{config.CUBE_QUEUE_PROCESSING_NAME}:monitor:{probe_suffix}"
    payload = json.dumps({"probe": probe_suffix}, ensure_ascii=False, separators=(",", ":"))

    try:
        client = _build_redis_client(config.CUBE_QUEUE_REDIS_URL)
        client.delete(ready_key, processing_key)
        client.lpush(ready_key, payload)
        moved_payload = _decode_redis_value(client.rpoplpush(ready_key, processing_key))
        removed = client.lrem(processing_key, 1, payload)
        if moved_payload != payload or removed != 1:
            raise RuntimeError("ready/processing queue roundtrip 결과가 예상과 다릅니다")
    except Exception as exc:
        return MonitorEntry(
            name="Cube Queue",
            backend="Redis",
            tone="error",
            status="failed",
            target=target,
            detail=f"큐 enqueue/dequeue/ack 검사 실패: {exc}.",
        )
    finally:
        if client is not None:
            try:
                client.delete(ready_key, processing_key)
            except Exception:
                pass
            _close_redis_client(client)

    return MonitorEntry(
        name="Cube Queue",
        backend="Redis",
        tone="ok",
        status="working",
        target=target,
        detail="큐 enqueue/dequeue/ack roundtrip 이 정상입니다.",
    )


def _check_cube_worker_daemon() -> MonitorEntry:
    return _check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=max(config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS * 3, _MIN_DAEMON_STALE_SECONDS),
    )


def _check_scheduler_lock() -> MonitorEntry:
    target = f"{config.SCHEDULER_LOCK_PREFIX.strip(':') or 'scheduler:lock'}:*"
    if not config.SCHEDULER_REDIS_URL:
        return MonitorEntry(
            name="Scheduler Lock",
            backend="Redis Lock",
            tone="error",
            status="not configured",
            target=target,
            detail="SCHEDULER_REDIS_URL 이 없어 스케줄러 분산 락을 사용할 수 없습니다.",
        )

    from api.scheduled_tasks import _lock as scheduler_lock

    client = None
    lock_key = scheduler_lock._scheduler_lock_key(f"monitor:{uuid4().hex}")
    lock = None

    try:
        client = _build_redis_client(config.SCHEDULER_REDIS_URL)
        lock = scheduler_lock._RedisDistributedLock(
            client=client,
            key=lock_key,
            ttl_seconds=max(1, min(config.SCHEDULER_LOCK_TTL_SECONDS, 30)),
            renew_interval_seconds=0,
        )
        if not lock.acquire():
            raise RuntimeError("lock acquire 가 false 를 반환했습니다")
        lock.lease.ensure_held()
        lock.release()
        if client.get(lock_key) is not None:
            raise RuntimeError("lock release 후 키가 남아 있습니다")
    except Exception as exc:
        return MonitorEntry(
            name="Scheduler Lock",
            backend="Redis Lock",
            tone="error",
            status="failed",
            target=target,
            detail=f"락 acquire/release 검사 실패: {exc}.",
        )
    finally:
        if client is not None:
            try:
                client.delete(lock_key)
            except Exception:
                pass
            _close_redis_client(client)

    return MonitorEntry(
        name="Scheduler Lock",
        backend="Redis Lock",
        tone="ok",
        status="working",
        target=target,
        detail="락 acquire/release 검사가 정상입니다.",
    )


def _check_file_delivery_metadata() -> MonitorEntry:
    from api.file_delivery import file_delivery_service

    backend = file_delivery_service._get_metadata_backend()
    probe_file_id = uuid4().hex
    metadata = {
        "file_id": probe_file_id,
        "filename": "monitor-probe.txt",
        "file_path": "/tmp/monitor-probe.txt",
        "content_type": "text/plain",
        "size_bytes": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "original_filename": "monitor-probe.txt",
        "stored_filename": "monitor-probe.txt",
        "user_id": "monitor",
        "user_storage_key": "monitor",
        "title": "monitor probe",
    }

    try:
        backend.set(probe_file_id, metadata)
        loaded = backend.get(probe_file_id)
        listed_ids = backend.list_ids()
        backend.delete(probe_file_id)
        deleted = backend.get(probe_file_id)
        if loaded != metadata or probe_file_id not in listed_ids or deleted is not None:
            raise RuntimeError("metadata roundtrip 결과가 예상과 다릅니다")
    except Exception as exc:
        return MonitorEntry(
            name="File Delivery Metadata",
            backend="Metadata",
            tone="error",
            status="failed",
            target="metadata store",
            detail=f"메타데이터 set/get/delete 검사 실패: {exc}.",
        )

    if isinstance(backend, file_delivery_service._RedisMetadataBackend):
        return MonitorEntry(
            name="File Delivery Metadata",
            backend="Redis",
            tone="ok",
            status="working",
            target="file_delivery:file:* / index",
            detail="메타데이터 set/get/delete roundtrip 이 정상입니다.",
        )

    detail = (
        "FILE_DELIVERY_REDIS_URL 이 없어 메모리 백엔드로 동작 중이며, "
        "메타데이터 set/get/delete roundtrip 은 정상입니다."
        if not config.FILE_DELIVERY_REDIS_URL
        else "Redis 백엔드를 사용할 수 없어 메모리 백엔드로 fallback 되었고, "
        "메타데이터 set/get/delete roundtrip 은 정상입니다."
    )
    return MonitorEntry(
        name="File Delivery Metadata",
        backend="Memory",
        tone="warning",
        status="fallback",
        target="in-memory metadata store",
        detail=detail,
    )


def _check_scheduler_worker_daemon() -> MonitorEntry:
    return _check_daemon_component(
        name="Scheduler Worker Daemon",
        event_names=("scheduler_worker_heartbeat", "scheduler_worker_started"),
        stale_after_seconds=max(config.SCHEDULER_WORKER_IDLE_SECONDS * 3, _MIN_DAEMON_STALE_SECONDS),
    )


def _build_redis_client(redis_url: str):
    import redis

    return redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)


def _close_redis_client(client) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def _decode_redis_value(value: bytes | str | None) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _check_daemon_component(
    *,
    name: str,
    event_names: tuple[str, ...],
    stale_after_seconds: int,
) -> MonitorEntry:
    latest_record = _read_latest_activity_record(event_names)
    if latest_record is None:
        return MonitorEntry(
            name=name,
            backend="Daemon",
            tone="error",
            status="not running",
            target=str(_activity_log_path()),
            detail="activity log에서 최근 시작/heartbeat 이벤트를 찾지 못했습니다.",
        )

    latest_event = latest_record.get("event", "unknown")
    latest_timestamp = _parse_activity_timestamp(latest_record.get("timestamp"))
    if latest_timestamp is None:
        return MonitorEntry(
            name=name,
            backend="Daemon",
            tone="error",
            status="stale",
            target=f"{latest_event} @ invalid timestamp",
            detail="activity log의 daemon 타임스탬프를 해석할 수 없습니다.",
        )

    age_seconds = max(0, int((datetime.now(UTC) - latest_timestamp).total_seconds()))
    pid = latest_record.get("pid")
    target = latest_event if pid is None else f"{latest_event} (pid={pid})"
    if age_seconds > stale_after_seconds:
        return MonitorEntry(
            name=name,
            backend="Daemon",
            tone="error",
            status="stale",
            target=target,
            detail=(
                f"최근 daemon 이벤트는 {latest_timestamp.astimezone().strftime('%Y-%m-%d %H:%M:%S')} "
                f"({age_seconds}초 전)입니다. heartbeat 기준 {stale_after_seconds}초를 초과했습니다."
            ),
        )

    return MonitorEntry(
        name=name,
        backend="Daemon",
        tone="ok",
        status="running",
        target=target,
        detail=(
            f"최근 daemon 이벤트는 {latest_timestamp.astimezone().strftime('%Y-%m-%d %H:%M:%S')} "
            f"({age_seconds}초 전)입니다."
        ),
    )


def _activity_log_path() -> Path:
    return get_theme_log_dir(config.ACTIVITY_LOG_THEME) / "activity.jsonl"


def _read_latest_activity_record(event_names: tuple[str, ...]) -> dict[str, object] | None:
    log_path = _activity_log_path()
    if not log_path.exists():
        return None

    recent_lines = deque(maxlen=_ACTIVITY_TAIL_LINES)
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            recent_lines.append(line)

    target_events = set(event_names)
    for raw_line in reversed(recent_lines):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if record.get("event") in target_events:
            return record
    return None


def _parse_activity_timestamp(raw_timestamp: object) -> datetime | None:
    if not isinstance(raw_timestamp, str) or not raw_timestamp:
        return None
    try:
        return datetime.fromisoformat(raw_timestamp)
    except ValueError:
        return None


def _mask_url(raw_url: str) -> str:
    if not raw_url:
        return "미설정"

    parts = urlsplit(raw_url)
    if not parts.scheme:
        return raw_url

    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"

    if parts.username:
        auth = parts.username
        if parts.password is not None:
            auth = f"{auth}:***"
        host = f"{auth}@{host}"

    return urlunsplit((parts.scheme, host, parts.path, "", ""))
