from unittest.mock import patch


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
                "name": "Primary Redis",
                "backend": "Redis",
                "tone": "error",
                "status": "unreachable",
                "target": "redis://cache:6379/0",
                "detail": "Redis ping failed",
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
    assert b"Primary Redis" in response.data
    assert b"Cube Worker Daemon" in response.data
    assert b"connected" in response.data
    assert b"unreachable" in response.data
    assert b"running" in response.data
    mock_get_monitoring_snapshot.assert_called_once_with()
