import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from api import config

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_initialized: set[str] = set()


def setup_logging() -> None:
    """Configure the root logger with a rotating file handler."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    _initialized.add("app")


def get_topic_logger(topic: str) -> logging.Logger:
    """Return a logger that writes to ``logs/{topic}.log``.

    Each topic gets its own rotating file handler (1-week retention).
    Safe to call multiple times — handlers are attached only once.
    """
    logger = logging.getLogger(f"topic.{topic}")

    if topic in _initialized:
        return logger

    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        log_dir / f"{topic}.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(handler)
    logger.propagate = False
    _initialized.add(topic)

    return logger
