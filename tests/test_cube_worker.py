import logging
from unittest.mock import patch

from api.cube.models import CubeIncomingMessage, CubeQueuedMessage
from api.cube.service import CubeUpstreamError
from api.cube.worker import process_next_queued_message


def _queued_message(*, attempt: int = 0) -> CubeQueuedMessage:
    return CubeQueuedMessage(
        incoming=CubeIncomingMessage(
            user_id="u1",
            user_name="tester",
            channel_id="c1",
            message_id="m1",
            message="hello",
        ),
        attempt=attempt,
    )


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.process_queued_message")
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_acknowledges_success(
    mock_dequeue,
    mock_process,
    mock_acknowledge,
    caplog,
):
    caplog.set_level(logging.INFO, logger="api.cube.worker")

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_dequeue.assert_called_once_with(timeout_seconds=0)
    mock_process.assert_called_once()
    mock_acknowledge.assert_called_once_with(_queued_message())
    assert "Cube worker processing started" in caplog.text
    assert "Cube worker processing completed" in caplog.text


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.requeue_queued_message")
@patch("api.cube.worker.process_queued_message", side_effect=CubeUpstreamError("LLM reply generation failed."))
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message())
def test_process_next_queued_message_requeues_retryable_failure(
    mock_dequeue,
    mock_process,
    mock_requeue,
    mock_acknowledge,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MAX_RETRIES", 3)
    caplog.set_level(logging.INFO, logger="api.cube.worker")

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_requeue.assert_called_once_with(_queued_message(), next_attempt=1)
    mock_acknowledge.assert_not_called()
    assert "Cube worker requeued message" in caplog.text


@patch("api.cube.worker.acknowledge_queued_message")
@patch("api.cube.worker.requeue_queued_message")
@patch("api.cube.worker.process_queued_message", side_effect=CubeUpstreamError("LLM reply generation failed."))
@patch("api.cube.worker.dequeue_queued_message", return_value=_queued_message(attempt=2))
def test_process_next_queued_message_drops_after_max_retries(
    mock_dequeue,
    mock_process,
    mock_requeue,
    mock_acknowledge,
    monkeypatch,
    caplog,
):
    failed_message = _queued_message(attempt=2)
    monkeypatch.setattr("api.cube.worker.config.CUBE_QUEUE_MAX_RETRIES", 3)
    caplog.set_level(logging.INFO, logger="api.cube.worker")

    assert process_next_queued_message(timeout_seconds=0) is True

    mock_requeue.assert_not_called()
    mock_acknowledge.assert_called_once_with(failed_message)
    assert "Cube worker failed message permanently" in caplog.text
