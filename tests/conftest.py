import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def app():
    """Create a Flask test app with chatbot blueprint."""
    from api import create_application

    app = create_application()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def file_delivery_env(monkeypatch, tmp_path):
    import api.file_delivery.file_delivery_service as file_delivery_service
    from api import config

    storage_dir = tmp_path / "file_delivery"

    monkeypatch.setattr(config, "FILE_DELIVERY_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(config, "FILE_DELIVERY_REDIS_URL", "")
    monkeypatch.setattr(config, "FILE_DELIVERY_BASE_URL", "http://testserver/file-delivery/files")
    monkeypatch.setattr(file_delivery_service, "_metadata_backend", None)
    monkeypatch.setattr(file_delivery_service, "_metadata_ttl_warning_emitted", False)

    yield storage_dir

    file_delivery_service._metadata_backend = None
    file_delivery_service._metadata_ttl_warning_emitted = False
