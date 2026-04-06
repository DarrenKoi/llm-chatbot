import importlib

from api import config


def test_config_defaults_use_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://primary")
    monkeypatch.delenv("SCHEDULER_REDIS_URL", raising=False)
    monkeypatch.delenv("FILE_DELIVERY_REDIS_URL", raising=False)

    reloaded = importlib.reload(config)
    try:
        assert reloaded.CUBE_QUEUE_REDIS_URL == "redis://primary"
        assert reloaded.SCHEDULER_REDIS_URL == "redis://primary"
        assert reloaded.FILE_DELIVERY_REDIS_URL == "redis://primary"
    finally:
        importlib.reload(reloaded)


def test_config_ignores_redis_fallback_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://primary")
    monkeypatch.setenv("REDIS_FALLBACK_URL", "redis://fallback")
    monkeypatch.delenv("SCHEDULER_REDIS_URL", raising=False)
    monkeypatch.delenv("FILE_DELIVERY_REDIS_URL", raising=False)

    reloaded = importlib.reload(config)
    try:
        assert reloaded.CUBE_QUEUE_REDIS_URL == "redis://primary"
        assert reloaded.SCHEDULER_REDIS_URL == "redis://primary"
        assert reloaded.FILE_DELIVERY_REDIS_URL == "redis://primary"
        assert not hasattr(reloaded, "REDIS_FALLBACK_URL")
    finally:
        importlib.reload(reloaded)


def test_cube_queue_redis_url_always_matches_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://primary")
    monkeypatch.setenv("CUBE_QUEUE_REDIS_URL", "redis://queue")

    reloaded = importlib.reload(config)
    try:
        assert reloaded.CUBE_QUEUE_REDIS_URL == "redis://primary"
    finally:
        importlib.reload(reloaded)


def test_file_delivery_base_url_defaults_to_web_app_url(monkeypatch):
    monkeypatch.setenv("WEB_APP_URL", "http://example-webapp")
    monkeypatch.delenv("FILE_DELIVERY_BASE_URL", raising=False)

    reloaded = importlib.reload(config)
    try:
        assert reloaded.WEB_APP_URL == "http://example-webapp"
        assert reloaded.FILE_DELIVERY_BASE_URL == "http://example-webapp/file-delivery/files"
    finally:
        importlib.reload(reloaded)
