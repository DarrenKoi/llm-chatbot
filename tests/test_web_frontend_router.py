"""Nuxt SPA 정적 파일 라우팅 동작 검증."""

from pathlib import Path
from unittest.mock import patch


def test_chat_returns_503_when_spa_not_deployed(client):
    response = client.get("/chat")
    assert response.status_code == 503


def test_chat_serves_index_html_when_built(client, tmp_path):
    static_root = tmp_path / "chat"
    static_root.mkdir()
    (static_root / "index.html").write_text("<html><body>chat</body></html>", encoding="utf-8")

    with patch("api.web_frontend.router._STATIC_ROOT", static_root):
        response = client.get("/chat")

    assert response.status_code == 200
    assert b"<html><body>chat</body></html>" in response.data


def test_unknown_chat_subpath_falls_back_to_index(client, tmp_path):
    static_root = tmp_path / "chat"
    static_root.mkdir()
    (static_root / "index.html").write_text("<html>fallback</html>", encoding="utf-8")

    with patch("api.web_frontend.router._STATIC_ROOT", static_root):
        response = client.get("/chat/threads/unknown-id")

    assert response.status_code == 200
    assert b"<html>fallback</html>" in response.data


def test_existing_static_file_is_served_directly(client, tmp_path):
    static_root = tmp_path / "chat"
    static_root.mkdir()
    (static_root / "index.html").write_text("idx", encoding="utf-8")
    (static_root / "robots.txt").write_text("User-agent: *", encoding="utf-8")

    with patch("api.web_frontend.router._STATIC_ROOT", static_root):
        response = client.get("/chat/robots.txt")

    assert response.status_code == 200
    assert b"User-agent: *" in response.data


def test_nuxt_assets_returns_404_when_missing(client, tmp_path):
    static_root = tmp_path / "chat"
    static_root.mkdir()
    (static_root / "index.html").write_text("idx", encoding="utf-8")

    with patch("api.web_frontend.router._STATIC_ROOT", static_root):
        with patch("api.web_frontend.router._NUXT_ASSET_DIR", static_root / "_nuxt"):
            response = client.get("/chat/_nuxt/missing.js")

    assert response.status_code == 404


def test_nuxt_assets_served_when_present(client, tmp_path):
    static_root = tmp_path / "chat"
    static_root.mkdir()
    (static_root / "index.html").write_text("idx", encoding="utf-8")
    asset_dir = static_root / "_nuxt"
    asset_dir.mkdir()
    (asset_dir / "app.js").write_text("console.log('app')", encoding="utf-8")

    with patch("api.web_frontend.router._STATIC_ROOT", static_root):
        with patch("api.web_frontend.router._NUXT_ASSET_DIR", asset_dir):
            response = client.get("/chat/_nuxt/app.js")

    assert response.status_code == 200
    assert b"console.log('app')" in response.data


def test_static_root_resolves_to_api_static_chat():
    from api.web_frontend import router

    expected = Path(__file__).resolve().parent.parent / "api" / "static" / "chat"
    assert router._STATIC_ROOT == expected
