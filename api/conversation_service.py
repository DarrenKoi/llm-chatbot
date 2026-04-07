from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from api import config
from api.workflows.langgraph_checkpoint import validate_mongo_storage_config

_backend = None


class ConversationStoreError(RuntimeError):
    """Raised when the configured conversation backend is unavailable."""


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    if config.AFM_MONGO_URI:
        from pymongo import MongoClient

        try:
            client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[config.AFM_DB_NAME]
            _backend = _MongoBackend(db)
        except Exception as exc:
            raise ConversationStoreError("Configured MongoDB conversation store is unavailable.") from exc
    if _backend is None:
        _backend = _InMemoryBackend()
    return _backend


def get_history(
    user_id: str,
    *,
    limit: int | None = None,
    conversation_id: str | None = None,
) -> list[dict[str, Any]]:
    return _get_backend().get(user_id, limit=limit, conversation_id=conversation_id)


def get_recent_messages(*, limit: int = 50) -> list[dict[str, Any]]:
    return _get_backend().get_recent(limit=limit)


def append_message(
    user_id: str,
    message: dict,
    *,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    _get_backend().append(user_id, message, conversation_id=conversation_id, metadata=metadata)


def append_messages(
    user_id: str,
    messages: list[dict],
    *,
    conversation_id: str | None = None,
):
    for msg in messages:
        _get_backend().append(user_id, msg, conversation_id=conversation_id)


class _MongoBackend:
    def __init__(self, db):
        collections = validate_mongo_storage_config()
        self._col = db[collections.conversation_history]
        self._col.create_index(
            [("user_id", 1), ("conversation_id", 1), ("created_at", -1)],
            background=True,
        )
        if config.CONVERSATION_TTL_SECONDS > 0:
            self._col.create_index(
                "created_at",
                expireAfterSeconds=config.CONVERSATION_TTL_SECONDS,
                background=True,
            )
        self._col.create_index(
            [("user_id", 1), ("conversation_id", 1), ("role", 1), ("message_id", 1)],
            unique=True,
            background=True,
            partialFilterExpression={"message_id": {"$exists": True}},
        )

    def get(
        self,
        user_id: str,
        *,
        limit: int | None = None,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        message_limit = config.CONVERSATION_MAX_MESSAGES if limit is None else max(1, limit)
        cursor = (
            self._col.find(
                _build_query(user_id, conversation_id),
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
                {"_id": 0, "user_id": 1, "conversation_id": 1, "role": 1, "content": 1},
            )
            .sort("created_at", -1)
            .limit(max(1, limit))
        )
        return list(cursor)

    def append(
        self,
        user_id: str,
        message: dict,
        *,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        from pymongo.errors import DuplicateKeyError

        document = _build_document(
            user_id,
            message,
            conversation_id=conversation_id,
            metadata=metadata,
        )
        try:
            self._col.insert_one(document)
        except DuplicateKeyError:
            return


class _InMemoryBackend:
    MAX_USERS = 1000
    MAX_RECENT_MESSAGES = 5000

    def __init__(self):
        self._store: OrderedDict[str, list[dict]] = OrderedDict()
        self._recent_messages: list[dict[str, Any]] = []

    def get(
        self,
        user_id: str,
        *,
        limit: int | None = None,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        store_key = _build_store_key(user_id, conversation_id)
        if store_key in self._store:
            self._store.move_to_end(store_key)
        messages = list(self._store.get(store_key, []))
        if limit is None:
            return messages
        return messages[-max(1, limit) :]

    def append(
        self,
        user_id: str,
        message: dict,
        *,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        store_key = _build_store_key(user_id, conversation_id)
        if store_key not in self._store:
            if len(self._store) >= self.MAX_USERS:
                self._store.popitem(last=False)
            self._store[store_key] = []
        self._store[store_key].append(dict(message))
        self._store[store_key] = self._store[store_key][-config.CONVERSATION_MAX_MESSAGES :]
        self._recent_messages.append(
            {
                "user_id": user_id,
                "conversation_id": _normalize_conversation_id(user_id, conversation_id),
                "role": message["role"],
                "content": message["content"],
            }
        )
        self._recent_messages = self._recent_messages[-self.MAX_RECENT_MESSAGES :]
        self._store.move_to_end(store_key)

    def get_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._recent_messages[-max(1, limit) :]))


def _normalize_conversation_id(user_id: str, conversation_id: str | None) -> str:
    return conversation_id or user_id


def _build_store_key(user_id: str, conversation_id: str | None) -> str:
    return f"{user_id}::{_normalize_conversation_id(user_id, conversation_id)}"


def _build_query(user_id: str, conversation_id: str | None) -> dict[str, Any]:
    # conversation_id를 생략하면 해당 사용자의 모든 대화를 반환한다.
    # _build_document는 항상 conversation_id를 정규화하여 저장하므로,
    # 특정 채널만 조회할 때는 conversation_id를 명시해야 한다.
    query: dict[str, Any] = {"user_id": user_id}
    if conversation_id:
        query["conversation_id"] = conversation_id
    return query


def _build_document(
    user_id: str,
    message: dict[str, Any],
    *,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "user_id": user_id,
        "conversation_id": _normalize_conversation_id(user_id, conversation_id),
        "role": message["role"],
        "content": message["content"],
        "created_at": datetime.now(UTC),
    }
    for key, value in (metadata or {}).items():
        if key in document or value is None:
            continue
        document[key] = value
    return document
