from api import config
from api.scheduled_tasks.scan_member_info import (
    get_next_hynix_member_info_batch,
    load_hynix_member_info_state,
    mark_hynix_member_info_completed,
    reset_hynix_member_info_state,
)


def setup_function():
    reset_hynix_member_info_state()


def teardown_function():
    reset_hynix_member_info_state()


def test_hynix_member_info_batch_advances_and_wraps(monkeypatch):
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_REDIS_URL", "")
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_BATCH_SIZE", 500)
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_STATE_KEY", "test:scan-member-info")

    first_batch = get_next_hynix_member_info_batch(total_count=1200)
    assert first_batch.offset == 0
    assert first_batch.limit == 500
    assert first_batch.cycle == 0

    state = mark_hynix_member_info_completed(total_count=1200, processed_count=500)
    assert state.next_offset == 500
    assert state.cycle == 0

    second_batch = get_next_hynix_member_info_batch(total_count=1200)
    assert second_batch.offset == 500
    assert second_batch.limit == 500
    assert second_batch.cycle == 0

    state = mark_hynix_member_info_completed(total_count=1200, processed_count=700)
    assert state.next_offset == 0
    assert state.cycle == 1

    wrapped_batch = get_next_hynix_member_info_batch(total_count=1200)
    assert wrapped_batch.offset == 0
    assert wrapped_batch.cycle == 1


def test_hynix_member_info_state_defaults_when_empty(monkeypatch):
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_REDIS_URL", "")
    monkeypatch.setattr(config, "SCAN_MEMBER_INFO_STATE_KEY", "test:scan-member-info-empty")

    state = load_hynix_member_info_state()

    assert state.next_offset == 0
    assert state.cycle == 0
    assert state.last_total_count == 0
