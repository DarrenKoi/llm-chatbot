from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

from api import config, create_application
from api.scheduled_tasks._lock import SchedulerLockLost
from api.scheduled_tasks.scan_member_info import task as scan_member_info_task


def test_create_application_skips_scheduler_by_default(monkeypatch):
    start_scheduler = MagicMock()
    monkeypatch.setattr(config, "APP_START_SCHEDULER", False)
    monkeypatch.setattr("api.start_scheduler", start_scheduler)

    create_application()

    start_scheduler.assert_not_called()


def test_create_application_can_start_scheduler_when_enabled(monkeypatch):
    start_scheduler = MagicMock()
    monkeypatch.setattr(config, "APP_START_SCHEDULER", True)
    monkeypatch.setattr("api.start_scheduler", start_scheduler)

    create_application()

    start_scheduler.assert_called_once()


def test_hynix_member_info_registers_job_when_enabled(monkeypatch):
    scheduler = MagicMock()
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_ENABLED", True)
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_INTERVAL_MINUTES", 432)

    scan_member_info_task.register(scheduler)

    scheduler.add_job.assert_called_once()
    kwargs = scheduler.add_job.call_args.kwargs
    assert kwargs["id"] == "hynix_member_info_batch"
    assert kwargs["trigger"] == "interval"
    assert kwargs["minutes"] == 432


def test_hynix_member_info_batch_job_skips_state_commit_after_lock_loss(monkeypatch):
    parsed_member_nos: list[int] = []
    completed_calls: list[dict] = []

    class _Lease:
        def __init__(self) -> None:
            self.calls = 0

        def ensure_held(self) -> None:
            self.calls += 1
            if self.calls >= 8:
                raise SchedulerLockLost("renewal failed")

    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_ENABLED", True)
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_BATCH_SIZE", 3)
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_DUMMY_TOTAL_COUNT", 3)
    monkeypatch.setattr(
        scan_member_info_task,
        "get_next_hynix_member_info_batch",
        lambda **_kwargs: SimpleNamespace(offset=0, limit=3, cycle=0),
    )
    monkeypatch.setattr(
        scan_member_info_task,
        "_parse_hynix_member_info",
        lambda member: parsed_member_nos.append(member["member_no"]),
    )
    monkeypatch.setattr(
        scan_member_info_task,
        "mark_hynix_member_info_completed",
        lambda **kwargs: completed_calls.append(kwargs),
    )

    with pytest.raises(SchedulerLockLost):
        scan_member_info_task.hynix_member_info_batch_job(lock_lease=_Lease())

    assert parsed_member_nos == [1, 2, 3]
    assert completed_calls == []
