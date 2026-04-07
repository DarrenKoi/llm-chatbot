from unittest.mock import patch


def test_main_page_renders_main_template(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Signal Room" in response.data
    assert b"Available Pages" in response.data
    assert b"/conversation" in response.data
    assert b"/monitor" in response.data
    assert b"/scheduled_tasks" in response.data
    assert b"/file_delivery" in response.data
    assert b"/workflows" in response.data


@patch("api.get_recent_messages", return_value=[{"user_id": "u1", "role": "user", "content": "hello"}])
def test_conversation_page_renders_recent_conversation(mock_get_recent_messages, client):
    response = client.get("/conversation")

    assert response.status_code == 200
    assert b"Conversation Debug" in response.data
    assert b"hello" in response.data
    assert b"u1" in response.data
    mock_get_recent_messages.assert_called_once_with(limit=50)


@patch(
    "api.get_monitoring_snapshot",
    return_value={
        "checked_at": "2026-04-01 12:34:56",
        "summary": {
            "healthy": 3,
            "warnings": 1,
            "errors": 2,
            "disabled": 1,
        },
        "entries": [
            {
                "name": "Conversation Store",
                "backend": "MongoDB",
                "tone": "ok",
                "status": "connected",
                "target": "mongodb://user:***@db-host:27017/",
                "detail": "MongoDB ping OK",
            },
            {
                "name": "Cube Queue",
                "backend": "Redis",
                "tone": "error",
                "status": "failed",
                "target": "cube:incoming / cube:incoming:processing",
                "detail": "큐 enqueue/dequeue/ack 검사 실패",
            },
            {
                "name": "Cube Worker Daemon",
                "backend": "Daemon",
                "tone": "ok",
                "status": "running",
                "target": "cube_worker_heartbeat (pid=321)",
                "detail": "최근 daemon 이벤트는 2026-04-01 12:34:30 (26초 전)입니다.",
            },
        ],
    },
)
def test_monitor_page_renders_db_status_table(mock_get_monitoring_snapshot, client):
    response = client.get("/monitor")

    assert response.status_code == 200
    assert b"Service Monitor" in response.data
    assert b"Conversation Store" in response.data
    assert b"Cube Queue" in response.data
    assert b"Cube Worker Daemon" in response.data
    assert b"connected" in response.data
    assert b"failed" in response.data
    assert b"running" in response.data
    mock_get_monitoring_snapshot.assert_called_once_with()


@patch(
    "api.get_scheduled_tasks_snapshot",
    return_value={
        "checked_at": "2026-04-02 15:30:00",
        "summary": {
            "configured_jobs": 2,
            "running_jobs": 1,
            "recent_failures": 1,
            "no_history": 0,
        },
        "worker": {
            "tone": "ok",
            "status": "running",
            "target": "scheduler_worker_heartbeat (pid=987)",
            "detail": "최근 worker 이벤트는 2026-04-02 15:29:42 (18초 전)입니다.",
        },
        "config": {
            "redis_url": "redis://scheduler-host:6379/0",
            "lock_prefix": "scheduler:sknn_v3",
            "lock_ttl_seconds": 3600,
            "renew_interval_seconds": 30,
            "misfire_grace_time_seconds": 60,
            "worker_idle_seconds": 60,
            "inspection_error": None,
            "lock_backend": {
                "tone": "ok",
                "status": "connected",
                "detail": "Scheduler Redis 락 상태를 확인했습니다.",
            },
        },
        "tasks": [
            {
                "id": "cleanup_uwsgi_logs",
                "callable": "api.scheduled_tasks.tasks.cleanup._cleanup_uwsgi_logs",
                "trigger": "cron[hour='1', minute='0']",
                "next_run_at": "2026-04-03 01:00:00",
                "uses_distributed_lock": True,
                "lock_key": "scheduler:sknn_v3:cleanup_uwsgi_logs",
                "runtime": {
                    "tone": "ok",
                    "status": "running",
                    "detail": "분산 락이 현재 잡혀 있습니다.",
                },
                "last_activity": {
                    "tone": "warning",
                    "status": "started",
                    "occurred_at": "2026-04-02 15:29:59",
                    "detail": "실행 시작",
                },
                "history": [
                    {
                        "tone": "warning",
                        "status": "started",
                        "occurred_at": "2026-04-02 15:29:59",
                        "detail": "실행 시작",
                    }
                ],
            },
            {
                "id": "cleanup_file_delivery",
                "callable": "api.scheduled_tasks.tasks.cleanup._cleanup_expired_file_delivery_files",
                "trigger": "cron[hour='1', minute='0']",
                "next_run_at": "2026-04-03 01:00:00",
                "uses_distributed_lock": True,
                "lock_key": "scheduler:sknn_v3:cleanup_file_delivery",
                "runtime": {
                    "tone": "disabled",
                    "status": "idle",
                    "detail": "현재 실행 중인 락은 없습니다.",
                },
                "last_activity": {
                    "tone": "error",
                    "status": "failed",
                    "occurred_at": "2026-04-02 02:00:03",
                    "detail": "실행 실패",
                },
                "history": [
                    {
                        "tone": "error",
                        "status": "failed",
                        "occurred_at": "2026-04-02 02:00:03",
                        "detail": "실행 실패",
                    }
                ],
            },
        ],
    },
)
def test_scheduled_tasks_page_renders_snapshot(mock_get_scheduled_tasks_snapshot, client):
    response = client.get("/scheduled_tasks")

    assert response.status_code == 200
    assert b"Scheduled Tasks" in response.data
    assert b"cleanup_uwsgi_logs" in response.data
    assert b"cleanup_file_delivery" in response.data
    assert b"running" in response.data
    assert b"failed" in response.data
    mock_get_scheduled_tasks_snapshot.assert_called_once_with()


def test_workflow_graph_page_uses_wide_layout(client):
    response = client.get("/workflows/translator")

    assert response.status_code == 200
    assert b"Workflow: translator" in response.data
    assert b"width: min(80vw, 1500px);" in response.data
    assert b"height: min(78vh, 920px) !important;" in response.data
