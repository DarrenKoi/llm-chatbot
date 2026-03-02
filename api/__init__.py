import logging

from flask import Flask

from api.routes import chatbot_bp
from api import config


def create_application() -> Flask:
    """Create and configure the Flask application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.register_blueprint(chatbot_bp)

    return app
