import json
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from api import config
from api.workflows.langgraph_checkpoint import validate_mongo_storage_config

_backend = None


class ConversationStoreError(RuntimeError):
    """Raised when the configured conversation backend is unavailable."""


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    backend_name = _resolve_backend_name()
    if backend_name == "mongo":
        from pymongo import MongoClient

        try:
            client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[config.AFM_DB_NAME]
            _backend = _MongoBackend(db)
        except Exception as exc:
            raise ConversationStoreError("Configured MongoDB conversation store is unavailable.") from exc
    elif backend_name == "local":
        _backend = _LocalFileBackend(config.CONVERSATION_LOCAL_DIR)
    else:
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
        self._message_sequence = 0

    def get(
        self,
        user_id: str,
        *,
        limit: int | None = None,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        messages = self._collect_messages(user_id, conversation_id=conversation_id)
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
        self._message_sequence += 1
        stored_message = dict(message)
        stored_message["_order"] = self._message_sequence
        self._store[store_key].append(stored_message)
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

    def _collect_messages(self, user_id: str, *, conversation_id: str | None = None) -> list[dict[str, Any]]:
        if conversation_id is not None:
            store_key = _build_store_key(user_id, conversation_id)
            if store_key in self._store:
                self._store.move_to_end(store_key)
            return _strip_message_metadata(self._store.get(store_key, []))
        prefix = f"{user_id}::"
        matching_keys = [key for key in self._store if key.startswith(prefix)]
        for key in matching_keys:
            self._store.move_to_end(key)
        messages: list[dict[str, Any]] = []
        for key in matching_keys:
            messages.extend(self._store.get(key, []))
        messages.sort(key=lambda message: message.get("_order", 0))
        return _strip_message_metadata(messages)


class _LocalFileBackend:
    def __init__(self, root_dir: Path):
        self._root_dir = root_dir

    def get(
        self,
        user_id: str,
        *,
        limit: int | None = None,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        messages = self._load_documents(user_id, conversation_id=conversation_id)
        message_limit = config.CONVERSATION_MAX_MESSAGES if limit is None else max(1, limit)
        return [{"role": message["role"], "content": message["content"]} for message in messages[-message_limit:]]

    def get_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        if not self._root_dir.exists():
            return []
        for path in self._root_dir.glob("*/*.jsonl"):
            documents.extend(self._read_documents(path))
        documents.sort(key=lambda document: document.get("created_at", ""))
        return [
            {
                "user_id": document["user_id"],
                "conversation_id": document["conversation_id"],
                "role": document["role"],
                "content": document["content"],
            }
            for document in reversed(documents[-max(1, limit) :])
        ]

    def append(
        self,
        user_id: str,
        message: dict,
        *,
        conversation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        document = _serialize_document(
            _build_document(
                user_id,
                message,
                conversation_id=conversation_id,
                metadata=metadata,
            )
        )
        if self._is_duplicate(user_id, document):
            return
        path = self._build_conversation_path(user_id, conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(document, ensure_ascii=False))
            handle.write("\n")

    def _load_documents(self, user_id: str, *, conversation_id: str | None = None) -> list[dict[str, Any]]:
        paths = (
            [self._build_conversation_path(user_id, conversation_id)]
            if conversation_id is not None
            else list(self._iter_user_paths(user_id))
        )
        documents: list[dict[str, Any]] = []
        for path in paths:
            documents.extend(self._read_documents(path))
        documents.sort(key=lambda document: document.get("created_at", ""))
        return documents

    def _iter_user_paths(self, user_id: str) -> list[Path]:
        user_dir = self._root_dir / _encode_path_segment(user_id)
        if not user_dir.exists():
            return []
        return sorted(user_dir.glob("*.jsonl"))

    def _build_conversation_path(self, user_id: str, conversation_id: str | None) -> Path:
        normalized_conversation_id = _normalize_conversation_id(user_id, conversation_id)
        user_dir = self._root_dir / _encode_path_segment(user_id)
        filename = f"{_encode_path_segment(normalized_conversation_id)}.jsonl"
        return user_dir / filename

    def _read_documents(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        documents: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                documents.append(payload)
        return documents

    def _is_duplicate(self, user_id: str, document: dict[str, Any]) -> bool:
        message_id = document.get("message_id")
        if not message_id:
            return False
        path = self._build_conversation_path(user_id, document.get("conversation_id"))
        for existing in self._read_documents(path):
            if existing.get("role") == document["role"] and existing.get("message_id") == message_id:
                return True
        return False


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


def _resolve_backend_name() -> str:
    backend_name = (config.CONVERSATION_BACKEND or "auto").strip().lower()
    if backend_name not in {"auto", "mongo", "local", "memory"}:
        raise ConversationStoreError(f"Unsupported conversation backend: {backend_name}")
    if backend_name == "auto":
        return "mongo" if config.AFM_MONGO_URI else "memory"
    if backend_name == "mongo" and not config.AFM_MONGO_URI:
        raise ConversationStoreError("CONVERSATION_BACKEND=mongo requires AFM_MONGO_URI.")
    return backend_name


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(document, ensure_ascii=False, default=_json_default))


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _encode_path_segment(value: str) -> str:
    return quote(value, safe="")


def _strip_message_metadata(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in (messages or [])
    ]


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
