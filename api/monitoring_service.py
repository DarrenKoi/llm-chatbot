from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from api import config

MonitorTone = Literal["ok", "warning", "error", "disabled"]


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
        _check_cube_queue_redis(),
        _check_scheduler_redis(),
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


def _check_cube_queue_redis() -> MonitorEntry:
    return _check_redis_component(
        name="Cube Queue",
        redis_url=config.CUBE_QUEUE_REDIS_URL,
        allow_fallback=False,
        empty_detail="CUBE_QUEUE_REDIS_URL 이 없어 비동기 Cube 큐를 사용할 수 없습니다.",
    )


def _check_scheduler_redis() -> MonitorEntry:
    if not config.APP_START_SCHEDULER:
        return MonitorEntry(
            name="Scheduler Lock",
            backend="Redis",
            tone="disabled",
            status="disabled",
            target=_mask_url(config.SCHEDULER_REDIS_URL),
            detail="웹 앱의 APP_START_SCHEDULER 가 꺼져 있습니다. dedicated scheduler_worker.py 를 별도 프로세스로 실행하는 구성이면 정상입니다.",
        )

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
