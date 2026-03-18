import json
import logging
from logging.handlers import TimedRotatingFileHandler

from api import config
from api.utils.logger import (
    get_theme_logger,
    get_topic_logger,
    log_activity,
    rollover_activity_logs,
    setup_logging,
)


def _remove_tagged_handlers(logger: logging.Logger) -> None:
    handlers = list(logger.handlers)
    for handler in handlers:
        if getattr(handler, "_chatbot_handler_tag", "").startswith("chatbot."):
            logger.removeHandler(handler)
            handler.close()


def _reset_logger_state() -> None:
    from api.utils.logger import service as _svc
    _svc._setup_done = False
    _remove_tagged_handlers(logging.getLogger())
    _remove_tagged_handlers(logging.getLogger("activity"))

    manager = logging.root.manager
    for name, logger_obj in manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger) and (name.startswith("topic.") or name.startswith("theme.")):
            _remove_tagged_handlers(logger_obj)


def _flush_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def test_log_activity_writes_json_line(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "ACTIVITY_LOG_THEME", "activity")
    monkeypatch.setattr(config, "LOG_RETENTION_DAYS", 7)
    monkeypatch.setattr(config, "APP_NAME", "chatbot-test")
    monkeypatch.setattr(config, "APP_ENV", "test")
    _reset_logger_state()

    setup_logging()
    log_activity(
        "request_accepted",
        user_id="u1",
        user_name="홍길동",
        status="ok",
        **{"meta.trace.id": "abc", "$type": "important"},
    )
    _flush_handlers(logging.getLogger("activity"))

    log_file = config.LOG_DIR / "activity" / "activity.jsonl"
    assert log_file.exists()

    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)
    assert payload["event"] == "request_accepted"
    assert payload["user_id"] == "u1"
    assert payload["user_name"] == "홍길동"
    assert payload["status"] == "ok"
    assert payload["level"] == "INFO"
    assert payload["service"] == "chatbot-test"
    assert payload["environment"] == "test"
    assert "@timestamp" in payload
    assert payload["meta_trace_id"] == "abc"
    assert payload["_type"] == "important"
    assert "홍길동" in first_line
    timed_handlers = [
        handler
        for handler in logging.getLogger("activity").handlers
        if isinstance(handler, TimedRotatingFileHandler)
    ]
    assert timed_handlers
    assert timed_handlers[0].backupCount == 7


def test_topic_json_logger_and_rollover(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "LOG_RETENTION_DAYS", 7)
    _reset_logger_state()

    topic_logger = get_topic_logger("jobs", json_output=True)
    topic_logger.info("jobs_event", extra={"activity_data": {"event": "jobs_event", "job_id": "daily-cleanup"}})
    _flush_handlers(topic_logger)

    topic_log_file = config.LOG_DIR / "jobs" / "jobs.jsonl"
    assert topic_log_file.exists()
    payload = json.loads(topic_log_file.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "jobs_event"
    assert payload["job_id"] == "daily-cleanup"
    timed_handlers = [handler for handler in topic_logger.handlers if isinstance(handler, TimedRotatingFileHandler)]
    assert timed_handlers
    assert timed_handlers[0].backupCount == 7

    assert rollover_activity_logs() >= 1


def test_theme_logger_writes_under_theme_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "LOG_RETENTION_DAYS", 7)
    _reset_logger_state()

    theme_logger = get_theme_logger("audit", name="security", json_output=False)
    theme_logger.info("access granted")
    _flush_handlers(theme_logger)

    themed_log_file = config.LOG_DIR / "audit" / "security.log"
    assert themed_log_file.exists()
    assert "access granted" in themed_log_file.read_text(encoding="utf-8")
