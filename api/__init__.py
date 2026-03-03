from flask import Flask

from api.routes import chatbot_bp
from api.utils.logger import setup_logging
from api.utils.scheduler import start_scheduler


def create_application() -> Flask:
    """Create and configure the Flask application."""
    setup_logging()
    start_scheduler()

    app = Flask(__name__)
    app.register_blueprint(chatbot_bp)

    return app
