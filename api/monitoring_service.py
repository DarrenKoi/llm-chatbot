import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from api import config
from api.utils.logger.paths import get_theme_log_dir

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
        _check_mongo_conversation_store(),
        _check_primary_redis(),
        _check_cube_worker_daemon(),
        _check_scheduler_redis(),
        _check_scheduler_worker_daemon(),
        _check_file_delivery_redis(),
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
    if not config.AFM_MONGO_URI:
        return MonitorEntry(
            name="Conversation Store",
            backend="MongoDB",
            tone="warning",
            status="fallback",
            target="미설정",
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
            tone="warning",
            status="fallback",
            target=_mask_url(config.AFM_MONGO_URI),
            detail=f"MongoDB ping 실패: {exc}. 앱은 메모리 대화 저장소로 fallback 됩니다.",
        )

    return MonitorEntry(
        name="Conversation Store",
        backend="MongoDB",
        tone="ok",
        status="connected",
        target=_mask_url(config.AFM_MONGO_URI),
        detail=f"DB `{config.AFM_DB_NAME}` 에 정상 연결되었습니다.",
    )


def _check_primary_redis() -> MonitorEntry:
    return _check_redis_component(
        name="Primary Redis",
        redis_url=config.REDIS_URL,
        allow_fallback=False,
        empty_detail="REDIS_URL 이 없어 Redis 기반 기능을 사용할 수 없습니다.",
    )


def _check_cube_worker_daemon() -> MonitorEntry:
    return _check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=max(config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS * 3, _MIN_DAEMON_STALE_SECONDS),
    )


def _check_scheduler_redis() -> MonitorEntry:
    return _check_redis_component(
        name="Scheduler Lock",
        redis_url=config.SCHEDULER_REDIS_URL,
        allow_fallback=False,
        empty_detail="SCHEDULER_REDIS_URL 이 없어 스케줄러 분산 락을 사용할 수 없습니다.",
    )


def _check_file_delivery_redis() -> MonitorEntry:
    return _check_redis_component(
        name="File Delivery Metadata",
        redis_url=config.FILE_DELIVERY_REDIS_URL,
        allow_fallback=True,
        empty_detail="FILE_DELIVERY_REDIS_URL 이 없어 파일 메타데이터는 메모리 백엔드로 동작합니다.",
    )


def _check_scheduler_worker_daemon() -> MonitorEntry:
    return _check_daemon_component(
        name="Scheduler Worker Daemon",
        event_names=("scheduler_worker_heartbeat", "scheduler_worker_started"),
        stale_after_seconds=max(config.SCHEDULER_WORKER_IDLE_SECONDS * 3, _MIN_DAEMON_STALE_SECONDS),
    )


def _check_redis_component(
    *,
    name: str,
    redis_url: str,
    allow_fallback: bool,
    empty_detail: str,
) -> MonitorEntry:
    if not redis_url:
        return MonitorEntry(
            name=name,
            backend="Redis",
            tone="warning" if allow_fallback else "error",
            status="fallback" if allow_fallback else "not configured",
            target="미설정",
            detail=empty_detail,
        )

    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            client.ping()
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
    except Exception as exc:
        return MonitorEntry(
            name=name,
            backend="Redis",
            tone="warning" if allow_fallback else "error",
            status="fallback" if allow_fallback else "unreachable",
            target=_mask_url(redis_url),
            detail=_build_redis_failure_detail(name=name, allow_fallback=allow_fallback, exc=exc),
        )

    return MonitorEntry(
        name=name,
        backend="Redis",
        tone="ok",
        status="connected",
        target=_mask_url(redis_url),
        detail="Redis ping 응답이 정상입니다.",
    )


def _build_redis_failure_detail(*, name: str, allow_fallback: bool, exc: Exception) -> str:
    if allow_fallback:
        return f"{name} Redis ping 실패: {exc}. 앱은 메모리 백엔드로 fallback 됩니다."
    return f"{name} Redis ping 실패: {exc}."


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

    age_seconds = max(0, int((datetime.now(timezone.utc) - latest_timestamp).total_seconds()))
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
