"""LangGraph MongoDB checkpointer helpers bound to AFM Mongo settings."""

from dataclasses import dataclass
from typing import Any

from api import config


@dataclass(frozen=True)
class LangGraphCheckpointMongo:
    client: Any
    database: Any


def open_langgraph_checkpoint_mongo() -> LangGraphCheckpointMongo:
    """Open the MongoDB database used by LangGraph checkpoints.

    The checkpointer must use the same MongoDB connection settings as the rest of
    the application, sourced from ``AFM_MONGO_URI`` and ``AFM_DB_NAME``.
    """

    if not config.AFM_MONGO_URI:
        raise RuntimeError("AFM_MONGO_URI is not configured.")
    if not config.AFM_DB_NAME:
        raise RuntimeError("AFM_DB_NAME is not configured.")

    from pymongo import MongoClient

    client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
    return LangGraphCheckpointMongo(client=client, database=client[config.AFM_DB_NAME])
