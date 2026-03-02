import logging
from datetime import datetime, timezone

from api import config

logger = logging.getLogger(__name__)

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    from pymongo import MongoClient
    client = MongoClient(config.MONGO_URL)
    db = client[config.MONGO_DB_NAME]
    _collection = db["request_logs"]
    return _collection


def log_request(doc: dict):
    """Insert a request log document into MongoDB.

    Never raises — logging failures are swallowed so they
    don't affect the main request flow.
    """
    try:
        doc.setdefault("created_at", datetime.now(timezone.utc))
        _get_collection().insert_one(doc)
    except Exception:
        logger.exception("Failed to write request log to MongoDB")
