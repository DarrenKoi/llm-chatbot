from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from api import config

_backend = None


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    if config.AFM_MONGO_URI:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure

        try:
            client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[config.AFM_DB_NAME]
            _backend = _MongoBackend(db)
        except ConnectionFailure:
            pass
    if _backend is None:
        _backend = _InMemoryBackend()
    return _backend


def get_history(user_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    return _get_backend().get(user_id, limit=limit)


def get_recent_messages(*, limit: int = 50) -> list[dict[str, Any]]:
    return _get_backend().get_recent(limit=limit)


def append_message(user_id: str, message: dict):
    _get_backend().append(user_id, message)


def append_messages(user_id: str, messages: list[dict]):
    for msg in messages:
        _get_backend().append(user_id, msg)


class _MongoBackend:
    COLLECTION = "cube_conversation_messages"

    def __init__(self, db):
        self._col = db[self.COLLECTION]
        self._col.create_index(
            [("user_id", 1), ("created_at", -1)],
            background=True,
        )

    def get(self, user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        message_limit = config.CONVERSATION_MAX_MESSAGES if limit is None else max(1, limit)
        cursor = (
            self._col.find(
                {"user_id": user_id},
                {"_id": 0, "role": 1, "content": 1},
            )
            .sort("created_at", -1)
            .limit(message_limit)
        )
        messages = list(cursor)
        messages.reverse()
        return messages

    def get_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        cursor = (
            self._col.find(
                {},
                {"_id": 0, "user_id": 1, "role": 1, "content": 1},
            )
            .sort("created_at", -1)
            .limit(max(1, limit))
        )
        return list(cursor)

    def append(self, user_id: str, message: dict):
        self._col.insert_one(
            {
                "user_id": user_id,
                "role": message["role"],
                "content": message["content"],
                "created_at": datetime.now(timezone.utc),
            }
        )


class _InMemoryBackend:
    MAX_USERS = 1000
    MAX_RECENT_MESSAGES = 5000

    def __init__(self):
        self._store: OrderedDict[str, list[dict]] = OrderedDict()
        self._recent_messages: list[dict[str, Any]] = []

    def get(self, user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        if user_id in self._store:
            self._store.move_to_end(user_id)
        messages = list(self._store.get(user_id, []))
        if limit is None:
            return messages
        return messages[-max(1, limit):]

    def append(self, user_id: str, message: dict):
        if user_id not in self._store:
            if len(self._store) >= self.MAX_USERS:
                self._store.popitem(last=False)
            self._store[user_id] = []
        self._store[user_id].append(message)
        self._store[user_id] = self._store[user_id][-config.CONVERSATION_MAX_MESSAGES:]
        self._recent_messages.append(
            {
                "user_id": user_id,
                "role": message["role"],
                "content": message["content"],
            }
        )
        self._recent_messages = self._recent_messages[-self.MAX_RECENT_MESSAGES:]
        self._store.move_to_end(user_id)

    def get_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._recent_messages[-max(1, limit):]))
