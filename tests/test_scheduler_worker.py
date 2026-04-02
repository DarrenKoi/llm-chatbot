from unittest.mock import MagicMock

from api import config, create_application


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
