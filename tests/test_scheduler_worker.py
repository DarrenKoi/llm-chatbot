from unittest.mock import MagicMock

from api import config, create_application
from api.utils.scheduler.tasks import hynix_member_info as hynix_member_info_task


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
    monkeypatch.setattr(config, "HYNIX_MEMBER_INFO_ENABLED", True)
    monkeypatch.setattr(config, "HYNIX_MEMBER_INFO_INTERVAL_MINUTES", 432)

    hynix_member_info_task.register(scheduler)

    scheduler.add_job.assert_called_once()
    kwargs = scheduler.add_job.call_args.kwargs
    assert kwargs["id"] == "hynix_member_info_batch"
    assert kwargs["trigger"] == "interval"
    assert kwargs["minutes"] == 432
