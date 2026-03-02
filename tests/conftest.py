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
