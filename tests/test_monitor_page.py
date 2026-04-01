from unittest.mock import patch


@patch(
    "api.get_monitoring_snapshot",
    return_value={
        "checked_at": "2026-04-01 12:34:56",
        "summary": {
            "healthy": 2,
            "warnings": 1,
            "errors": 1,
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
                "status": "unreachable",
                "target": "redis://cache:6379/0",
                "detail": "Redis ping failed",
            },
        ],
    },
)
def test_monitor_page_renders_db_status_table(mock_get_monitoring_snapshot, client):
    response = client.get("/monitor")

    assert response.status_code == 200
    assert b"DB Monitor" in response.data
    assert b"Conversation Store" in response.data
    assert b"Cube Queue" in response.data
    assert b"connected" in response.data
    assert b"unreachable" in response.data
    mock_get_monitoring_snapshot.assert_called_once_with()
