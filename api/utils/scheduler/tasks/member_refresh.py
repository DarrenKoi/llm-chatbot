import logging
from datetime import datetime, timezone

from api import config
from api.member_refresh import get_next_member_refresh_batch, mark_member_refresh_completed
from api.utils.scheduler._lock import run_locked_job

logger = logging.getLogger(__name__)


def _get_total_member_count() -> int:
    """Return the current total member count from the source system."""
    raise NotImplementedError("Implement _get_total_member_count() for your member source.")


def _load_member_batch(*, offset: int, limit: int) -> list[dict]:
    """
    Load the next deterministic slice of members to parse.

    Replace this stub with your real member source query. The source query should:
    1. Return members in stable order.
    2. Support offset/limit paging.
    """
    raise NotImplementedError("Implement _load_member_batch() for your member source.")


def _parse_member(member: dict) -> None:
    """Replace this stub with the actual member parsing/upsert logic."""
    raise NotImplementedError("Implement _parse_member() for your member parser.")


def member_refresh_batch_job() -> None:
    if not config.MEMBER_REFRESH_ENABLED:
        logger.info("Skipping member refresh batch: MEMBER_REFRESH_ENABLED is disabled.")
        return

    if config.MEMBER_REFRESH_BATCH_SIZE <= 0:
        logger.warning("Skipping member refresh batch: MEMBER_REFRESH_BATCH_SIZE must be positive.")
        return

    started_at = datetime.now(timezone.utc).isoformat()
    total_count = _get_total_member_count()
    if total_count <= 0:
        logger.info("Skipping member refresh batch: source returned no members.")
        return

    batch = get_next_member_refresh_batch(total_count=total_count, batch_size=config.MEMBER_REFRESH_BATCH_SIZE)
    members = _load_member_batch(offset=batch.offset, limit=batch.limit)

    processed_count = 0
    for member in members:
        _parse_member(member)
        processed_count += 1

    state = mark_member_refresh_completed(
        total_count=total_count,
        processed_count=processed_count,
        started_at=started_at,
    )
    logger.info(
        "Member refresh batch completed: processed=%s offset=%s next_offset=%s total=%s cycle=%s",
        processed_count,
        batch.offset,
        state.next_offset,
        total_count,
        state.cycle,
    )


def register(scheduler) -> None:
    if not config.MEMBER_REFRESH_ENABLED:
        logger.info("Member refresh scheduler job is disabled.")
        return

    def _run() -> None:
        run_locked_job("member_refresh_batch", member_refresh_batch_job)

    scheduler.add_job(
        _run,
        id="member_refresh_batch",
        trigger="interval",
        minutes=config.MEMBER_REFRESH_INTERVAL_MINUTES,
        replace_existing=True,
    )
