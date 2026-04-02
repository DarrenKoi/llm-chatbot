from datetime import datetime, timedelta, timezone

from api import monitoring_service


def test_check_daemon_component_reports_running_for_recent_heartbeat(monkeypatch, tmp_path):
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text(
        (
            '{"event":"cube_worker_started","timestamp":"2026-04-02T13:00:00+00:00","pid":101}\n'
            f'{{"event":"cube_worker_heartbeat","timestamp":"{datetime.now(timezone.utc).isoformat()}","pid":101}}\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "ok"
    assert entry.status == "running"
    assert "pid=101" in entry.target


def test_check_daemon_component_reports_stale_for_old_heartbeat(monkeypatch, tmp_path):
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text(
        f'{{"event":"scheduler_worker_heartbeat","timestamp":"{stale_timestamp}","pid":202}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Scheduler Worker Daemon",
        event_names=("scheduler_worker_heartbeat", "scheduler_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "error"
    assert entry.status == "stale"
    assert "pid=202" in entry.target


def test_check_daemon_component_reports_not_running_without_activity(monkeypatch, tmp_path):
    log_path = tmp_path / "activity.jsonl"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(monitoring_service, "_activity_log_path", lambda: log_path)

    entry = monitoring_service._check_daemon_component(
        name="Cube Worker Daemon",
        event_names=("cube_worker_heartbeat", "cube_worker_started"),
        stale_after_seconds=180,
    )

    assert entry.tone == "error"
    assert entry.status == "not running"
