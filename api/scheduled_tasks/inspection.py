import json
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from api import config
from api.scheduled_tasks._lock import _scheduler_lock_key
from api.scheduled_tasks._registry import _RUNTIME_META_ATTR, _TASK_META_ATTR, discover_and_register
from api.utils.logger.paths import get_theme_log_dir

_ACTIVITY_TAIL_LINES = 800
_MIN_WORKER_STALE_SECONDS = 180
_TASK_EVENT_ORDER = (
    "scheduled_task_started",
    "scheduled_task_completed",
    "scheduled_task_failed",
    "scheduled_task_aborted",
    "scheduled_task_skipped",
)
_TASK_EVENT_META = {
    "scheduled_task_started": {"status": "started", "tone": "warning"},
    "scheduled_task_completed": {"status": "completed", "tone": "ok"},
    "scheduled_task_failed": {"status": "failed", "tone": "error"},
    "scheduled_task_aborted": {"status": "aborted", "tone": "error"},
    "scheduled_task_skipped": {"status": "skipped", "tone": "warning"},
}


def get_scheduled_tasks_snapshot() -> dict[str, Any]:
    activity_records = _read_activity_records()
    worker = _build_scheduler_worker_snapshot(activity_records)
    task_histories = _build_task_history_map(activity_records)
    jobs, inspection_error = _collect_registered_jobs()
    lock_backend = _read_lock_backend_snapshot(jobs)

    tasks = [
        _build_task_snapshot(
            job=job,
            worker=worker,
            history=task_histories.get(job["id"], []),
            lock_state=lock_backend["locks"].get(job["id"]),
            lock_backend=lock_backend,
        )
        for job in jobs
    ]

    recent_failure_count = sum(1 for task in tasks if task["last_activity"]["status"] in {"failed", "aborted"})
    no_history_count = sum(1 for task in tasks if task["last_activity"]["status"] == "no history")

    return {
        "checked_at": _format_local_datetime(datetime.now(UTC)),
        "summary": {
            "configured_jobs": len(tasks),
            "running_jobs": sum(task["runtime"]["status"] == "running" for task in tasks),
            "recent_failures": recent_failure_count,
            "no_history": no_history_count,
        },
        "worker": worker,
        "config": {
            "redis_url": _mask_url(config.SCHEDULER_REDIS_URL),
            "lock_prefix": config.SCHEDULER_LOCK_PREFIX.strip(":") or "scheduler:lock",
            "lock_ttl_seconds": config.SCHEDULER_LOCK_TTL_SECONDS,
            "renew_interval_seconds": config.SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS,
            "misfire_grace_time_seconds": config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS,
            "worker_idle_seconds": config.SCHEDULER_WORKER_IDLE_SECONDS,
            "inspection_error": inspection_error,
            "lock_backend": {
                "tone": lock_backend["tone"],
                "status": lock_backend["status"],
                "detail": lock_backend["detail"],
            },
        },
        "tasks": tasks,
    }


def _collect_registered_jobs() -> tuple[list[dict[str, Any]], str | None]:
    scheduler = BackgroundScheduler(
        daemon=True,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS,
        },
    )
    scheduler_logger = logging.getLogger("apscheduler.scheduler")
    previous_level = scheduler_logger.level
    try:
        scheduler_logger.setLevel(logging.WARNING)
        discover_and_register(scheduler)

        jobs: list[dict[str, Any]] = []
        for job in scheduler.get_jobs():
            runtime_meta = getattr(job.func, _RUNTIME_META_ATTR, {})
            declared_meta = getattr(job.func, _TASK_META_ATTR, {})
            uses_distributed_lock = runtime_meta.get(
                "use_distributed_lock",
                declared_meta.get("use_distributed_lock", False),
            )
            lock_id = runtime_meta.get("lock_id") or declared_meta.get("lock_id") or job.id
            jobs.append(
                {
                    "id": job.id,
                    "callable": _callable_name(job.func, runtime_meta=runtime_meta),
                    "trigger": str(job.trigger),
                    "next_run_at": _format_local_datetime(_get_job_next_run_time(job)),
                    "uses_distributed_lock": uses_distributed_lock,
                    "lock_id": lock_id,
                    "lock_key": _scheduler_lock_key(lock_id) if uses_distributed_lock else "-",
                }
            )
        jobs.sort(key=lambda item: item["id"])
        return jobs, None
    except Exception as exc:
        return [], str(exc)
    finally:
        scheduler_logger.setLevel(previous_level)


def _callable_name(func, *, runtime_meta: dict[str, Any]) -> str:
    source = runtime_meta.get("source")
    if isinstance(source, str) and source:
        return source
    return f"{func.__module__}.{func.__qualname__}"


def _get_job_next_run_time(job) -> datetime | None:
    next_run_time = getattr(job, "next_run_time", None)
    if next_run_time is not None:
        return next_run_time

    trigger_timezone = getattr(job.trigger, "timezone", UTC)
    try:
        now = datetime.now(trigger_timezone)
    except Exception:
        now = datetime.now(UTC)

    try:
        return job.trigger.get_next_fire_time(None, now)
    except Exception:
        return None


def _read_lock_backend_snapshot(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    if not config.SCHEDULER_REDIS_URL:
        return {
            "tone": "error",
            "status": "not configured",
            "detail": "SCHEDULER_REDIS_URL 이 없어 실행 중인 잡 락 상태를 확인할 수 없습니다.",
            "locks": {},
        }

    try:
        import redis

        client = redis.from_url(config.SCHEDULER_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    except Exception as exc:
        return {
            "tone": "error",
            "status": "unavailable",
            "detail": f"Scheduler Redis 연결 초기화 실패: {exc}",
            "locks": {},
        }

    try:
        locks: dict[str, dict[str, Any]] = {}
        for job in jobs:
            if not job["uses_distributed_lock"]:
                continue
            value = client.get(job["lock_key"])
            ttl_ms = _read_lock_ttl_ms(client, job["lock_key"])
            locks[job["id"]] = {
                "held": value is not None,
                "key": job["lock_key"],
                "ttl_ms": ttl_ms,
            }
        return {
            "tone": "ok",
            "status": "connected",
            "detail": "Scheduler Redis 락 상태를 확인했습니다.",
            "locks": locks,
        }
    except Exception as exc:
        return {
            "tone": "error",
            "status": "failed",
            "detail": f"Scheduler Redis 조회 실패: {exc}",
            "locks": {},
        }
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _read_lock_ttl_ms(client, key: str) -> int | None:
    ttl = getattr(client, "pttl", None)
    if not callable(ttl):
        return None

    ttl_ms = ttl(key)
    if not isinstance(ttl_ms, int) or ttl_ms < 0:
        return None
    return ttl_ms


def _build_task_snapshot(
    *,
    job: dict[str, Any],
    worker: dict[str, Any],
    history: list[dict[str, Any]],
    lock_state: dict[str, Any] | None,
    lock_backend: dict[str, Any],
) -> dict[str, Any]:
    runtime = _build_runtime_snapshot(job=job, worker=worker, lock_state=lock_state, lock_backend=lock_backend)
    last_activity = history[0] if history else _build_empty_activity()

    return {
        "id": job["id"],
        "callable": job["callable"],
        "trigger": job["trigger"],
        "next_run_at": job["next_run_at"],
        "uses_distributed_lock": job["uses_distributed_lock"],
        "lock_key": job["lock_key"],
        "runtime": runtime,
        "last_activity": last_activity,
        "history": history[:4],
    }


def _build_runtime_snapshot(
    *,
    job: dict[str, Any],
    worker: dict[str, Any],
    lock_state: dict[str, Any] | None,
    lock_backend: dict[str, Any],
) -> dict[str, str]:
    if job["uses_distributed_lock"]:
        if lock_backend["tone"] == "error":
            return {
                "tone": "error",
                "status": "unknown",
                "detail": lock_backend["detail"],
            }
        if lock_state and lock_state["held"]:
            ttl_detail = ""
            if lock_state["ttl_ms"] is not None:
                ttl_detail = f" · TTL 약 {max(1, lock_state['ttl_ms'] // 1000)}초"
            return {
                "tone": "ok",
                "status": "running",
                "detail": f"분산 락이 현재 잡혀 있습니다 ({lock_state['key']}{ttl_detail}).",
            }

    if worker["status"] != "running":
        return {
            "tone": worker["tone"],
            "status": "worker down",
            "detail": "전용 scheduler worker heartbeat 가 정상 상태가 아니어서 다음 실행을 보장할 수 없습니다.",
        }

    return {
        "tone": "disabled",
        "status": "idle",
        "detail": "현재 실행 중인 락은 없으며 다음 스케줄을 기다리는 상태입니다.",
    }


def _build_empty_activity() -> dict[str, str]:
    return {
        "tone": "disabled",
        "status": "no history",
        "occurred_at": "-",
        "detail": "activity log 에 기록된 최근 실행 이력이 아직 없습니다.",
    }


def _build_scheduler_worker_snapshot(records: list[dict[str, Any]]) -> dict[str, str]:
    target_events = {"scheduler_worker_heartbeat", "scheduler_worker_started"}
    latest = next((record for record in reversed(records) if record.get("event") in target_events), None)
    log_path = str(_activity_log_path())
    if latest is None:
        return {
            "tone": "error",
            "status": "not running",
            "target": log_path,
            "detail": "scheduler worker 시작/heartbeat 이벤트를 찾지 못했습니다.",
        }

    timestamp = _parse_timestamp(latest.get("timestamp"))
    event_name = str(latest.get("event") or "unknown")
    pid = latest.get("pid")
    target = event_name if pid is None else f"{event_name} (pid={pid})"
    if timestamp is None:
        return {
            "tone": "error",
            "status": "stale",
            "target": target,
            "detail": "scheduler worker 이벤트 타임스탬프를 해석할 수 없습니다.",
        }

    age_seconds = max(0, int((datetime.now(UTC) - timestamp).total_seconds()))
    stale_after_seconds = max(config.SCHEDULER_WORKER_IDLE_SECONDS * 3, _MIN_WORKER_STALE_SECONDS)
    if age_seconds > stale_after_seconds:
        return {
            "tone": "error",
            "status": "stale",
            "target": target,
            "detail": (
                f"최근 worker 이벤트는 {_format_local_datetime(timestamp)} "
                f"({age_seconds}초 전)이며, stale 기준 {stale_after_seconds}초를 넘었습니다."
            ),
        }

    return {
        "tone": "ok",
        "status": "running",
        "target": target,
        "detail": f"최근 worker 이벤트는 {_format_local_datetime(timestamp)} ({age_seconds}초 전)입니다.",
    }


def _build_task_history_map(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in reversed(records):
        event_name = record.get("event")
        if event_name not in _TASK_EVENT_ORDER:
            continue
        job_id = record.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            continue
        histories[job_id].append(_format_task_activity(record))
    return histories


def _format_task_activity(record: dict[str, Any]) -> dict[str, str]:
    event_name = str(record["event"])
    event_meta = _TASK_EVENT_META[event_name]
    return {
        "tone": event_meta["tone"],
        "status": event_meta["status"],
        "occurred_at": _format_local_datetime(_parse_timestamp(record.get("timestamp"))),
        "detail": _format_task_activity_detail(record),
    }


def _format_task_activity_detail(record: dict[str, Any]) -> str:
    event_name = str(record["event"])
    reason = str(record.get("reason") or "").strip()
    error = str(record.get("error") or "").strip()
    duration_ms = record.get("duration_ms")
    lock_key = str(record.get("lock_key") or "").strip()

    if event_name == "scheduled_task_started":
        return f"실행 시작{_join_suffix(lock_key and f'락 {lock_key}')}"
    if event_name == "scheduled_task_completed":
        return f"정상 종료{_join_suffix(_format_duration(duration_ms), lock_key and f'락 {lock_key}')}"
    if event_name == "scheduled_task_failed":
        return f"실행 실패{_join_suffix(_format_duration(duration_ms), error)}"
    if event_name == "scheduled_task_aborted":
        return f"실행 중단{_join_suffix(_format_duration(duration_ms), _describe_reason(reason), error)}"
    if event_name == "scheduled_task_skipped":
        return f"실행 건너뜀{_join_suffix(_describe_reason(reason), lock_key and f'락 {lock_key}')}"
    return event_name


def _describe_reason(reason: str) -> str:
    if reason == "lock_held":
        return "다른 worker가 락을 이미 보유 중"
    if reason == "redis_unavailable":
        return "Redis lock backend unavailable"
    if reason == "lock_lost":
        return "락 소유권 상실"
    return reason


def _join_suffix(*parts: str) -> str:
    filtered = [part for part in parts if part]
    if not filtered:
        return ""
    return " · " + " · ".join(filtered)


def _format_duration(duration_ms: object) -> str:
    if not isinstance(duration_ms, int):
        return ""
    return f"{duration_ms}ms"


def _read_activity_records() -> list[dict[str, Any]]:
    log_path = _activity_log_path()
    if not log_path.exists():
        return []

    recent_lines = deque(maxlen=_ACTIVITY_TAIL_LINES)
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            recent_lines.append(line)

    records: list[dict[str, Any]] = []
    for raw_line in recent_lines:
        try:
            parsed = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _activity_log_path() -> Path:
    return get_theme_log_dir(config.ACTIVITY_LOG_THEME) / "activity.jsonl"


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_local_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _mask_url(raw_url: str) -> str:
    if not raw_url:
        return "미설정"
    try:
        from urllib.parse import urlsplit, urlunsplit

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
    except Exception:
        return raw_url
