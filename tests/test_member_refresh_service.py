from api.member_refresh import (
    get_next_member_refresh_batch,
    load_member_refresh_state,
    mark_member_refresh_completed,
    reset_member_refresh_state,
)
from api import config


def setup_function():
    reset_member_refresh_state()


def teardown_function():
    reset_member_refresh_state()


def test_member_refresh_batch_advances_and_wraps(monkeypatch):
    monkeypatch.setattr(config, "MEMBER_REFRESH_REDIS_URL", "")
    monkeypatch.setattr(config, "MEMBER_REFRESH_BATCH_SIZE", 500)
    monkeypatch.setattr(config, "MEMBER_REFRESH_STATE_KEY", "test:member-refresh")

    first_batch = get_next_member_refresh_batch(total_count=1200)
    assert first_batch.offset == 0
    assert first_batch.limit == 500
    assert first_batch.cycle == 0

    state = mark_member_refresh_completed(total_count=1200, processed_count=500)
    assert state.next_offset == 500
    assert state.cycle == 0

    second_batch = get_next_member_refresh_batch(total_count=1200)
    assert second_batch.offset == 500
    assert second_batch.limit == 500
    assert second_batch.cycle == 0

    state = mark_member_refresh_completed(total_count=1200, processed_count=700)
    assert state.next_offset == 0
    assert state.cycle == 1

    wrapped_batch = get_next_member_refresh_batch(total_count=1200)
    assert wrapped_batch.offset == 0
    assert wrapped_batch.cycle == 1


def test_member_refresh_state_defaults_when_empty(monkeypatch):
    monkeypatch.setattr(config, "MEMBER_REFRESH_REDIS_URL", "")
    monkeypatch.setattr(config, "MEMBER_REFRESH_STATE_KEY", "test:member-refresh-empty")

    state = load_member_refresh_state()

    assert state.next_offset == 0
    assert state.cycle == 0
    assert state.last_total_count == 0
