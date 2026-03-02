import sys
from pathlib import Path

import pytest
from flask import Flask

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def app():
    """Create a Flask test app with chatbot blueprint."""
    from index import chatbot_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(chatbot_bp)
    return app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()
