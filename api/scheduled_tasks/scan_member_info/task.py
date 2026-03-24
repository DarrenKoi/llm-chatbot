import logging
from datetime import datetime, timezone

from api import config
from api.scheduled_tasks.scan_member_info import get_next_hynix_member_info_batch, mark_hynix_member_info_completed
from api.scheduled_tasks._lock import run_locked_job

logger = logging.getLogger(__name__)


def _get_total_hynix_member_count() -> int:
    return max(0, config.HYNIX_MEMBER_INFO_DUMMY_TOTAL_COUNT)


def _load_hynix_member_batch(*, offset: int, limit: int, total_count: int) -> list[dict]:
    if total_count <= 0 or limit <= 0:
        return []

    upper_bound = min(offset + limit, total_count)
    members: list[dict] = []
    for index in range(offset, upper_bound):
        member_no = index + 1
        members.append(
            {
                "member_no": member_no,
                "employee_id": f"EMP{member_no:05d}",
                "name": f"Dummy Member {member_no}",
                "email": f"dummy{member_no}@example.com",
            }
        )
    return members


def _parse_hynix_member_info(member: dict) -> None:
    logger.info(
        "Dummy hynix member info parsed: employee_id=%s name=%s",
        member["employee_id"],
        member["name"],
    )


def hynix_member_info_batch_job() -> None:
    if not config.HYNIX_MEMBER_INFO_ENABLED:
        logger.info("Skipping hynix member info batch: HYNIX_MEMBER_INFO_ENABLED is disabled.")
        return

    if config.HYNIX_MEMBER_INFO_BATCH_SIZE <= 0:
        logger.warning("Skipping hynix member info batch: HYNIX_MEMBER_INFO_BATCH_SIZE must be positive.")
        return

    total_count = _get_total_hynix_member_count()
    if total_count <= 0:
        logger.info("Skipping hynix member info batch: dummy source returned no members.")
        return

    started_at = datetime.now(timezone.utc).isoformat()
    batch = get_next_hynix_member_info_batch(
        total_count=total_count,
        batch_size=config.HYNIX_MEMBER_INFO_BATCH_SIZE,
    )
    members = _load_hynix_member_batch(offset=batch.offset, limit=batch.limit, total_count=total_count)

    for member in members:
        _parse_hynix_member_info(member)

    state = mark_hynix_member_info_completed(
        total_count=total_count,
        processed_count=len(members),
        started_at=started_at,
    )
    logger.info(
        "Hynix member info batch completed: processed=%s start_member_no=%s next_offset=%s total=%s cycle=%s",
        len(members),
        batch.offset + 1,
        state.next_offset,
        total_count,
        state.cycle,
    )


def register(scheduler) -> None:
    if not config.HYNIX_MEMBER_INFO_ENABLED:
        logger.info("Hynix member info scheduler job is disabled.")
        return

    def _run() -> None:
        run_locked_job("hynix_member_info_batch", hynix_member_info_batch_job)

    scheduler.add_job(
        _run,
        id="hynix_member_info_batch",
        trigger="interval",
        minutes=config.HYNIX_MEMBER_INFO_INTERVAL_MINUTES,
        replace_existing=True,
    )
