import json
from io import BytesIO
from unittest.mock import patch

import pytest
import api.services.cdn.cdn_service as cdn_service
from api import config
from api.routes import _extract_image_url


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_receive_cube_missing_message(client):
    resp = client.post(
        "/api/v1/receive/cube",
        json={"user_id": "u1", "channel_id": "c1"},
    )
    assert resp.status_code == 400


@patch("api.routes.send_rich_notification")
@patch("api.routes.chat")
@patch("api.routes.append_messages")
@patch("api.routes.append_message")
@patch("api.routes.get_history", return_value=[])
def test_receive_cube_valid(
    mock_get_hist, mock_append, mock_append_multi,
    mock_chat, mock_send, client,
):
    mock_chat.return_value = ("Hello!", [{"role": "assistant", "content": "Hello!"}], {"llm_calls": [], "tool_executions": []})

    # Run synchronously by replacing executor.submit with direct call
    with patch("api.routes.executor") as mock_executor:
        mock_executor.submit.side_effect = lambda fn, *args: fn(*args)
        resp = client.post(
            "/api/v1/receive/cube",
            json={"user_id": "u1", "channel_id": "c1", "message": "Hi"},
        )

    assert resp.status_code == 202
    mock_get_hist.assert_called_once_with("u1")
    mock_append.assert_called_once()
    mock_chat.assert_called_once()
    mock_send.assert_called_once_with("c1", "Hello!", image_url=None)


def test_extract_image_url_found():
    messages = [
        {"role": "assistant", "content": "Here's the chart"},
        {"role": "tool", "content": json.dumps({"image_url": "http://example.com/chart.png"})},
    ]
    assert _extract_image_url(messages) == "http://example.com/chart.png"


def test_extract_image_url_not_found():
    messages = [
        {"role": "assistant", "content": "No chart here"},
        {"role": "tool", "content": json.dumps({"result": "data"})},
    ]
    assert _extract_image_url(messages) is None


def test_extract_image_url_invalid_json():
    messages = [{"role": "tool", "content": "not json"}]
    assert _extract_image_url(messages) is None


def test_cdn_upload_and_get_image(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    cdn_service._metadata_backend = None

    # 1x1 transparent PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(png_bytes), "dot.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201

    payload = upload.get_json()
    assert payload["file_id"]
    assert payload["file_url"].endswith(payload["file_id"])

    download = client.get(f"/cdn/files/{payload['file_id']}")
    assert download.status_code == 200
    assert download.mimetype == "image/png"
    assert download.data == png_bytes


def test_cdn_upload_missing_file(client):
    resp = client.post("/api/v1/cdn/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_cdn_upload_invalid_extension(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    cdn_service._metadata_backend = None

    resp = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(b"hello"), "note.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_cdn_resize_image(client, monkeypatch, tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    monkeypatch.setattr(config, "CDN_MAX_RESIZE_WIDTH", 2048)
    monkeypatch.setattr(config, "CDN_MAX_RESIZE_HEIGHT", 2048)
    cdn_service._metadata_backend = None

    src = image_module.new("RGB", (300, 150), color="red")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    upload = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(src_buffer.getvalue()), "source.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    file_id = upload.get_json()["file_id"]

    resized = client.get(f"/cdn/files/{file_id}?w=120")
    assert resized.status_code == 200

    resized_img = image_module.open(BytesIO(resized.data))
    assert resized_img.size[0] <= 120
    assert resized_img.size[1] < 150


def test_cdn_thumbnail_image(client, monkeypatch, tmp_path):
    image_module = pytest.importorskip("PIL.Image")

    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    monkeypatch.setattr(config, "CDN_THUMBNAIL_WIDTH", 64)
    monkeypatch.setattr(config, "CDN_THUMBNAIL_HEIGHT", 64)
    monkeypatch.setattr(config, "CDN_MAX_RESIZE_WIDTH", 2048)
    monkeypatch.setattr(config, "CDN_MAX_RESIZE_HEIGHT", 2048)
    cdn_service._metadata_backend = None

    src = image_module.new("RGB", (500, 300), color="blue")
    src_buffer = BytesIO()
    src.save(src_buffer, format="PNG")

    upload = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(src_buffer.getvalue()), "source.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    file_id = upload.get_json()["file_id"]

    thumb = client.get(f"/cdn/files/{file_id}?thumbnail=true")
    assert thumb.status_code == 200

    thumb_img = image_module.open(BytesIO(thumb.data))
    assert thumb_img.size[0] <= 64
    assert thumb_img.size[1] <= 64


def test_cdn_resize_invalid_query(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    cdn_service._metadata_backend = None

    # upload minimal valid png
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00"
        b"\x00\x02\x00\x01\xe5'\xd4\xa2\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(png_bytes), "dot.png")},
        content_type="multipart/form-data",
    )
    file_id = upload.get_json()["file_id"]

    bad = client.get(f"/cdn/files/{file_id}?w=abc")
    assert bad.status_code == 400

    bad_mix = client.get(f"/cdn/files/{file_id}?thumbnail=true&w=10")
    assert bad_mix.status_code == 400


def test_cdn_upload_docx(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CDN_STORAGE_DIR", tmp_path / "cdn")
    monkeypatch.setattr(config, "CDN_REDIS_URL", "")
    monkeypatch.setattr(config, "CDN_ALLOWED_EXTENSIONS", ("png", "jpg", "jpeg", "gif", "webp", "xlsx", "pptx", "docx"))
    cdn_service._metadata_backend = None

    docx_bytes = b"PK\x03\x04fake-docx-content-for-testing"
    upload = client.post(
        "/api/v1/cdn/upload",
        data={"file": (BytesIO(docx_bytes), "report.docx")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201

    payload = upload.get_json()
    assert payload["file_id"]
    assert payload["file_url"].endswith(payload["file_id"])

    download = client.get(f"/cdn/files/{payload['file_id']}")
    assert download.status_code == 200
    assert download.data == docx_bytes
    assert "attachment" in download.headers.get("Content-Disposition", "")
