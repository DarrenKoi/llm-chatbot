import os
import sys
from pathlib import Path

import pytest

# 테스트는 개발자 로컬 .env가 monkeypatch한 환경변수를 덮어쓰지 않도록 dotenv override를 끈다.
# (config.py의 load_dotenv(override=...) 기본값은 프로덕션용 True)
os.environ.setdefault("DOTENV_OVERRIDE", "false")

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def app(monkeypatch):
    """Create a Flask test app with chatbot blueprint."""
    from api import config, create_application

    # 기동 시 LLM 헬스체크가 테스트마다 네트워크를 건드리거나 대기하지 않도록 끈다.
    monkeypatch.setattr(config, "LLM_HEALTHCHECK_ON_STARTUP", False)

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
