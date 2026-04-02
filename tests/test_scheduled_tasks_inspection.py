from datetime import datetime, timedelta, timezone

from api import config
from api.scheduled_tasks import inspection


def test_collect_registered_jobs_lists_cleanup_tasks(monkeypatch):
    monkeypatch.setattr(config, "SCHEDULER_JOB_MISFIRE_GRACE_SECONDS", 60)
    monkeypatch.setattr(config, "SCHEDULER_LOCK_PREFIX", "scheduler:sknn_v3")

    jobs, error = inspection._collect_registered_jobs()

    assert error is None
    assert {job["id"] for job in jobs} == {"cleanup_file_delivery", "cleanup_uwsgi_logs"}
    assert all(job["uses_distributed_lock"] is True for job in jobs)
    assert {job["lock_key"] for job in jobs} == {
        "scheduler:sknn_v3:cleanup_file_delivery",
        "scheduler:sknn_v3:cleanup_uwsgi_logs",
    }


def test_get_scheduled_tasks_snapshot_builds_runtime_and_history(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        inspection,
        "_read_activity_records",
        lambda: [
            {
                "event": "scheduler_worker_heartbeat",
                "timestamp": (now - timedelta(seconds=10)).isoformat(),
                "pid": 123,
            },
            {
                "event": "scheduled_task_completed",
                "timestamp": (now - timedelta(seconds=20)).isoformat(),
                "job_id": "cleanup_uwsgi_logs",
                "lock_key": "scheduler:sknn_v3:cleanup_uwsgi_logs",
                "duration_ms": 250,
            },
            {
                "event": "scheduled_task_failed",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "job_id": "cleanup_file_delivery",
                "lock_key": "scheduler:sknn_v3:cleanup_file_delivery",
                "duration_ms": 1000,
                "error": "boom",
            },
        ],
    )
    monkeypatch.setattr(
        inspection,
        "_collect_registered_jobs",
        lambda: (
            [
                {
                    "id": "cleanup_uwsgi_logs",
                    "callable": "api.scheduled_tasks.tasks.cleanup._cleanup_uwsgi_logs",
                    "trigger": "cron[hour='1', minute='0']",
                    "next_run_at": "2026-04-03 01:00:00",
                    "uses_distributed_lock": True,
                    "lock_id": "cleanup_uwsgi_logs",
                    "lock_key": "scheduler:sknn_v3:cleanup_uwsgi_logs",
                },
                {
                    "id": "cleanup_file_delivery",
                    "callable": "api.scheduled_tasks.tasks.cleanup._cleanup_expired_file_delivery_files",
                    "trigger": "cron[hour='2', minute='0']",
                    "next_run_at": "2026-04-03 02:00:00",
                    "uses_distributed_lock": True,
                    "lock_id": "cleanup_file_delivery",
                    "lock_key": "scheduler:sknn_v3:cleanup_file_delivery",
                },
            ],
            None,
        ),
    )
    monkeypatch.setattr(
        inspection,
        "_read_lock_backend_snapshot",
        lambda _jobs: {
            "tone": "ok",
            "status": "connected",
            "detail": "Scheduler Redis 락 상태를 확인했습니다.",
            "locks": {
                "cleanup_uwsgi_logs": {
                    "held": True,
                    "key": "scheduler:sknn_v3:cleanup_uwsgi_logs",
                    "ttl_ms": 15000,
                },
                "cleanup_file_delivery": {
                    "held": False,
                    "key": "scheduler:sknn_v3:cleanup_file_delivery",
                    "ttl_ms": None,
                },
            },
        },
    )

    snapshot = inspection.get_scheduled_tasks_snapshot()

    assert snapshot["summary"] == {
        "configured_jobs": 2,
        "running_jobs": 1,
        "recent_failures": 1,
        "no_history": 0,
    }

    first_task = snapshot["tasks"][0]
    second_task = snapshot["tasks"][1]

    assert first_task["id"] == "cleanup_uwsgi_logs"
    assert first_task["runtime"]["status"] == "running"
    assert "TTL" in first_task["runtime"]["detail"]
    assert first_task["last_activity"]["status"] == "completed"

    assert second_task["id"] == "cleanup_file_delivery"
    assert second_task["runtime"]["status"] == "idle"
    assert second_task["last_activity"]["status"] == "failed"
    assert "boom" in second_task["last_activity"]["detail"]
