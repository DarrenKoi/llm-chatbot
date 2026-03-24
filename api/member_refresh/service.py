import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from api import config

logger = logging.getLogger(__name__)

_backend = None
_in_memory_state: dict[str, str] = {}


@dataclass
class MemberRefreshState:
    next_offset: int = 0
    cycle: int = 0
    last_total_count: int = 0
    last_batch_size: int = 0
    last_started_at: str | None = None
    last_finished_at: str | None = None


@dataclass(frozen=True)
class MemberRefreshBatch:
    offset: int
    limit: int
    cycle: int


class _InMemoryStateBackend:
    def get(self, key: str) -> str | None:
        return _in_memory_state.get(key)

    def set(self, key: str, value: str) -> None:
        _in_memory_state[key] = value


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend

    redis_url = config.MEMBER_REFRESH_REDIS_URL
    if not redis_url:
        _backend = _InMemoryStateBackend()
        return _backend

    try:
        import redis

        _backend = redis.from_url(redis_url)
        return _backend
    except Exception:
        logger.exception("Failed to initialize member refresh state backend. Falling back to in-memory state.")
        _backend = _InMemoryStateBackend()
        return _backend


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_non_negative(value: int) -> int:
    return max(0, int(value))


def load_member_refresh_state() -> MemberRefreshState:
    raw = _get_backend().get(config.MEMBER_REFRESH_STATE_KEY)
    if not raw:
        return MemberRefreshState()

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Invalid member refresh state payload. Resetting stored state.")
        return MemberRefreshState()

    return MemberRefreshState(
        next_offset=_normalize_non_negative(payload.get("next_offset", 0)),
        cycle=_normalize_non_negative(payload.get("cycle", 0)),
        last_total_count=_normalize_non_negative(payload.get("last_total_count", 0)),
        last_batch_size=_normalize_non_negative(payload.get("last_batch_size", 0)),
        last_started_at=payload.get("last_started_at"),
        last_finished_at=payload.get("last_finished_at"),
    )


def save_member_refresh_state(state: MemberRefreshState) -> MemberRefreshState:
    payload = json.dumps(asdict(state), ensure_ascii=False)
    _get_backend().set(config.MEMBER_REFRESH_STATE_KEY, payload)
    return state


def get_next_member_refresh_batch(total_count: int, *, batch_size: int | None = None) -> MemberRefreshBatch:
    if total_count <= 0:
        raise ValueError("total_count must be positive")

    effective_batch_size = _normalize_non_negative(batch_size or config.MEMBER_REFRESH_BATCH_SIZE)
    if effective_batch_size <= 0:
        raise ValueError("batch_size must be positive")

    state = load_member_refresh_state()
    offset = state.next_offset % total_count
    limit = min(effective_batch_size, total_count)
    return MemberRefreshBatch(offset=offset, limit=limit, cycle=state.cycle)


def mark_member_refresh_completed(
    *,
    total_count: int,
    processed_count: int,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> MemberRefreshState:
    if total_count <= 0:
        raise ValueError("total_count must be positive")

    processed = min(_normalize_non_negative(processed_count), total_count)
    state = load_member_refresh_state()
    current_offset = state.next_offset % total_count
    next_offset = current_offset + processed
    next_cycle = state.cycle

    if next_offset >= total_count and processed > 0:
        next_offset %= total_count
        next_cycle += 1

    return save_member_refresh_state(
        MemberRefreshState(
            next_offset=next_offset,
            cycle=next_cycle,
            last_total_count=total_count,
            last_batch_size=processed,
            last_started_at=started_at or _utc_now_iso(),
            last_finished_at=finished_at or _utc_now_iso(),
        )
    )


def reset_member_refresh_state() -> None:
    global _backend
    _backend = None
    _in_memory_state.clear()
