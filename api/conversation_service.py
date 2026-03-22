from collections import OrderedDict
from datetime import datetime, timezone

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


def get_history(user_id: str) -> list[dict]:
    return _get_backend().get(user_id)


def append_message(user_id: str, message: dict):
    _get_backend().append(user_id, message)


def append_messages(user_id: str, messages: list[dict]):
    for msg in messages:
        _get_backend().append(user_id, msg)


class _MongoBackend:
    COLLECTION = "conversation_messages"

    def __init__(self, db):
        self._col = db[self.COLLECTION]
        self._col.create_index(
            [("user_id", 1), ("created_at", -1)],
            background=True,
        )

    def get(self, user_id: str) -> list[dict]:
        cursor = (
            self._col.find(
                {"user_id": user_id},
                {"_id": 0, "role": 1, "content": 1},
            )
            .sort("created_at", -1)
            .limit(config.CONVERSATION_MAX_MESSAGES)
        )
        messages = list(cursor)
        messages.reverse()
        return messages

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

    def __init__(self):
        self._store: OrderedDict[str, list[dict]] = OrderedDict()

    def get(self, user_id: str) -> list[dict]:
        if user_id in self._store:
            self._store.move_to_end(user_id)
        return list(self._store.get(user_id, []))

    def append(self, user_id: str, message: dict):
        if user_id not in self._store:
            if len(self._store) >= self.MAX_USERS:
                self._store.popitem(last=False)
            self._store[user_id] = []
        self._store[user_id].append(message)
        self._store[user_id] = self._store[user_id][-config.CONVERSATION_MAX_MESSAGES:]
        self._store.move_to_end(user_id)
