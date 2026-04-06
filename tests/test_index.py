from io import BytesIO

import pytest

import api.file_delivery.file_delivery_service as file_delivery_service
from api import config


def _set_lastuser_cookie(client, user_id: str = "cube.user") -> None:
    client.set_cookie("LASTUSER", user_id)


def test_cdn_upload_and_get_image(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_BASE_URL",
        "http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com/file-delivery/files",
    )
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    # 1x1 transparent PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(png_bytes), "dot.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201

    payload = upload.get_json()
    assert payload["file_id"]
    assert (
        payload["file_url"]
        == f"http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com/file-delivery/files/{payload['file_id']}"
    )
    assert payload["stored_filename"].endswith(".png")

    download = client.get(f"/file-delivery/files/{payload['file_id']}")
    assert download.status_code == 200
    assert download.mimetype == "image/png"
    assert download.data == png_bytes

    download = client.get(f"/file_delivery/files/{payload['file_id']}")
    assert download.status_code == 200
    assert download.mimetype == "image/png"
    assert download.data == png_bytes


def test_cdn_upload_missing_file(client):
    resp = client.post("/api/v1/file_delivery/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_cdn_upload_invalid_extension(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    resp = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(b"hello"), "note.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_cdn_resize_image(client, monkeypatch, tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_WIDTH", 2048)
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_HEIGHT", 2048)
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    src = image_module.new("RGB", (300, 150), color="red")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(src_buffer.getvalue()), "source.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    file_id = upload.get_json()["file_id"]

    resized = client.get(f"/file_delivery/files/{file_id}?w=120")
    assert resized.status_code == 200

    resized_img = image_module.open(BytesIO(resized.data))
    assert resized_img.size[0] <= 120
    assert resized_img.size[1] < 150


def test_cdn_thumbnail_image(client, monkeypatch, tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(config, "FILE_DELIVERY_THUMBNAIL_WIDTH", 64)
    monkeypatch.setattr(config, "FILE_DELIVERY_THUMBNAIL_HEIGHT", 64)
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_WIDTH", 2048)
    monkeypatch.setattr(config, "FILE_DELIVERY_MAX_RESIZE_HEIGHT", 2048)
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    src = image_module.new("RGB", (500, 300), color="blue")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(src_buffer.getvalue()), "source.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    file_id = upload.get_json()["file_id"]

    thumb = client.get(f"/file_delivery/files/{file_id}?thumbnail=true")
    assert thumb.status_code == 200

    thumb_img = image_module.open(BytesIO(thumb.data))
    assert thumb_img.size[0] <= 64
    assert thumb_img.size[1] <= 64


def test_cdn_resize_invalid_query(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    # upload minimal valid png
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(png_bytes), "dot.png")},
        content_type="multipart/form-data",
    )
    file_id = upload.get_json()["file_id"]

    bad = client.get(f"/file_delivery/files/{file_id}?w=abc")
    assert bad.status_code == 400

    bad_mix = client.get(f"/file_delivery/files/{file_id}?thumbnail=true&w=10")
    assert bad_mix.status_code == 400


def test_cdn_upload_docx(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"),
    )
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    docx_bytes = b"PK\x03\x04fake-docx-content-for-testing"
    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(docx_bytes), "report.docx")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201

    payload = upload.get_json()
    assert payload["file_id"]
    assert payload["file_url"].endswith(payload["file_id"])

    download = client.get(f"/file_delivery/files/{payload['file_id']}")
    assert download.status_code == 200
    assert download.data == docx_bytes
    assert "attachment" in download.headers.get("Content-Disposition", "")


def test_file_delivery_upload_ignores_form_user_id_and_uses_cookie_user(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    file_delivery_service._metadata_backend = None
    _set_lastuser_cookie(client)

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={
            "file": (BytesIO(png_bytes), "report.png"),
            "user_id": "user.alpha@corp",
            "title": "월간 보고서 1Q",
        },
        content_type="multipart/form-data",
    )

    assert upload.status_code == 201
    payload = upload.get_json()
    metadata = file_delivery_service.get_file_metadata(payload["file_id"])

    assert payload["user_id"] == "cube.user"
    assert "cube.user" in payload["stored_filename"]
    assert "user.alpha-corp" not in payload["stored_filename"]
    assert payload["stored_filename"].endswith(".png")
    assert metadata is not None
    assert metadata["user_id"] == "cube.user"


def test_file_delivery_upload_rejects_missing_lastuser_cookie(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    file_delivery_service._metadata_backend = None

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(png_bytes), "cookie.png")},
        content_type="multipart/form-data",
    )

    assert upload.status_code == 400
    assert upload.get_json() == {"error": "Unable to resolve user from session"}


def test_file_delivery_upload_uses_lastuser_cookie_for_storage_path(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    file_delivery_service._metadata_backend = None

    _set_lastuser_cookie(client)

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload = client.post(
        "/api/v1/file_delivery/upload",
        data={"file": (BytesIO(png_bytes), "cookie.png")},
        content_type="multipart/form-data",
    )

    assert upload.status_code == 201
    payload = upload.get_json()
    metadata = file_delivery_service.get_file_metadata(payload["file_id"])

    assert payload["user_id"] == "cube.user"
    assert metadata is not None
    assert metadata["user_id"] == "cube.user"
    assert "/original/cube.user/" in metadata["file_path"]


def test_file_delivery_list_files_for_user_returns_recent_items(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", tmp_path / "file_delivery")
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(
        config,
        "FILE_DELIVERY_ALLOWED_EXTENSIONS",
        ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"),
    )
    file_delivery_service._metadata_backend = None

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
