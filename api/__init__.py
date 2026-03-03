import logging
from pathlib import Path

from flask import Flask

from api.routes import chatbot_bp
from api import config


def _setup_logging() -> None:
    """Configure logging: file handler for production, stderr for local dev."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)


def create_application() -> Flask:
    """Create and configure the Flask application."""
    _setup_logging()

    app = Flask(__name__)
    app.register_blueprint(chatbot_bp)

    return app
