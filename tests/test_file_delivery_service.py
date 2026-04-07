from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from api import config
from api.file_delivery import file_delivery_service


def test_list_files_for_user_returns_recent_items(file_delivery_env, monkeypatch):
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"),
    )

    first = file_delivery_service.save_file_bytes(
        data=b"first",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="first.docx",
        user_id="cube.user",
        title="first",
    )
    second = file_delivery_service.save_file_bytes(
        data=b"second",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="second.docx",
        user_id="cube.user",
        title="second",
    )
    file_delivery_service.save_file_bytes(
        data=b"other",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="other.docx",
        user_id="other.user",
        title="other",
    )

    files = file_delivery_service.list_files_for_user("cube.user", limit=10)

    assert [item["file_id"] for item in files] == [second["file_id"], first["file_id"]]


def test_get_expired_file_ids_returns_only_old_entries(file_delivery_env, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"),
    )

    stale = file_delivery_service.save_file_bytes(
        data=b"stale",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="stale.docx",
        user_id="cube.user",
    )
    fresh = file_delivery_service.save_file_bytes(
        data=b"fresh",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="fresh.docx",
        user_id="cube.user",
    )

    backend = file_delivery_service._get_metadata_backend()
    reference_time = datetime(2026, 4, 7, tzinfo=UTC)
    backend._store[stale["file_id"]]["created_at"] = (reference_time - timedelta(days=31)).isoformat()
    backend._store[fresh["file_id"]]["created_at"] = (reference_time - timedelta(days=5)).isoformat()

    assert file_delivery_service.get_expired_file_ids(reference_time=reference_time) == [stale["file_id"]]


def test_get_expired_file_ids_ignores_invalid_created_at(file_delivery_env, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"),
    )

    invalid = file_delivery_service.save_file_bytes(
        data=b"invalid",
        extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="invalid.docx",
        user_id="cube.user",
    )

    backend = file_delivery_service._get_metadata_backend()
    backend._store[invalid["file_id"]]["created_at"] = "not-a-date"

    assert file_delivery_service.get_expired_file_ids(reference_time=datetime(2026, 4, 7, tzinfo=UTC)) == []


def test_metadata_ttl_seconds_uses_retention_when_ttl_is_shorter(monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_RETENTION_DAYS", 21)
    monkeypatch.setattr(config, "FILE_DELIVERY_IMAGE_TTL_SECONDS", 3600)
    monkeypatch.setattr(file_delivery_service, "_metadata_ttl_warning_emitted", False)

    assert file_delivery_service._metadata_ttl_seconds() == 21 * 24 * 60 * 60


def test_metadata_ttl_seconds_keeps_explicit_ttl_when_it_exceeds_retention(monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_RETENTION_DAYS", 21)
    monkeypatch.setattr(config, "FILE_DELIVERY_IMAGE_TTL_SECONDS", 30 * 24 * 60 * 60)

    assert file_delivery_service._metadata_ttl_seconds() == 30 * 24 * 60 * 60


def test_delete_file_removes_original_variant_and_metadata(file_delivery_env):
    image_module = pytest.importorskip("PIL.Image")

    src = image_module.new("RGB", (300, 150), color="green")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    stored = file_delivery_service.save_file_bytes(
        data=src_buffer.getvalue(),
        extension="png",
        content_type="image/png",
        original_filename="source.png",
        user_id="cube.user",
    )

    original_path = Path(stored["file_path"])
    variant_path, _ = file_delivery_service.get_file_variant(stored["file_id"], width=120)

    assert original_path.exists()
    assert variant_path.exists()
    assert file_delivery_service.get_file_metadata(stored["file_id"]) is not None

    assert file_delivery_service.delete_file(stored["file_id"]) is True
    assert not original_path.exists()
    assert not variant_path.exists()
    assert file_delivery_service.get_file_metadata(stored["file_id"]) is None


def test_delete_file_returns_false_when_metadata_is_missing(file_delivery_env):
    assert file_delivery_service.delete_file("f" * 32) is False


def test_get_file_variant_returns_none_for_invalid_or_missing_file_id(file_delivery_env):
    assert file_delivery_service.get_file_variant("invalid-id") is None
    assert file_delivery_service.get_file_variant("f" * 32) is None


def test_get_file_variant_rejects_invalid_resize_options(file_delivery_env, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_WIDTH", 100)
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_HEIGHT", 100)

    image_module = pytest.importorskip("PIL.Image")
    src = image_module.new("RGB", (300, 150), color="orange")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    stored = file_delivery_service.save_file_bytes(
        data=src_buffer.getvalue(),
        extension="png",
        content_type="image/png",
        original_filename="source.png",
        user_id="cube.user",
    )

    with pytest.raises(ValueError, match="thumbnail cannot be combined with w/h options"):
        file_delivery_service.get_file_variant(stored["file_id"], width=10, thumbnail=True)

    with pytest.raises(ValueError, match="w must be <= 100"):
        file_delivery_service.get_file_variant(stored["file_id"], width=101)
