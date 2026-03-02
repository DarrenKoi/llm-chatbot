from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


@patch("services.log_service._get_collection")
def test_log_request_success(mock_get_coll):
    mock_coll = MagicMock()
    mock_get_coll.return_value = mock_coll

    from services.log_service import log_request
    doc = {"user_id": "u1", "status": "success"}
    log_request(doc)

    mock_coll.insert_one.assert_called_once()
    inserted = mock_coll.insert_one.call_args[0][0]
    assert inserted["user_id"] == "u1"
    assert "created_at" in inserted


@patch("services.log_service._get_collection")
def test_log_request_preserves_existing_timestamp(mock_get_coll):
    mock_coll = MagicMock()
    mock_get_coll.return_value = mock_coll

    from services.log_service import log_request
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    doc = {"user_id": "u1", "created_at": ts}
    log_request(doc)

    inserted = mock_coll.insert_one.call_args[0][0]
    assert inserted["created_at"] == ts


@patch("services.log_service._get_collection")
def test_log_request_swallows_exceptions(mock_get_coll):
    mock_coll = MagicMock()
    mock_coll.insert_one.side_effect = Exception("DB down")
    mock_get_coll.return_value = mock_coll

    from services.log_service import log_request
    # Should not raise
    log_request({"user_id": "u1"})
