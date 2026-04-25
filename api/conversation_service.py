import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from api import config
from api.workflows.langgraph_checkpoint import validate_mongo_storage_config

_backend = None

_PREVIEW_MAX_LENGTH = 120


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """대화 목록 한 건의 요약 정보."""

    user_id: str
    conversation_id: str
    last_message_at: str
    last_message_role: str
    last_message_preview: str
    source: str | None


class ConversationStoreError(RuntimeError):
    """Raised when the configured conversation backend is unavailable."""


def _get_backend():
    """설정에 따라 대화 이력 백엔드(MongoDB / 로컬파일 / 메모리)를 초기화하고 반환한다.

    첫 호출 시 백엔드를 생성해 캐시하며, 이후 호출은 캐시된 인스턴스를 재사용한다.
    """
    global _backend
    if _backend is not None:
        return _backend
    backend_name = _resolve_backend_name()
    if backend_name == "mongo":
        from api.mongo import get_mongo_client

        try:
            client = get_mongo_client()
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
    """특정 사용자의 대화 이력을 반환한다.

    conversation_id를 지정하면 해당 채널(채널 ID = conversation_id)의 이력만,
    생략하면 해당 사용자의 모든 대화 이력을 합쳐서 반환한다.
    limit을 지정하면 최신 메시지 기준으로 잘라낸다.
    """
    return _get_backend().get(user_id, limit=limit, conversation_id=conversation_id)


def get_recent_messages(*, limit: int = 50) -> list[dict[str, Any]]:
    """사용자 구분 없이 전체 최근 메시지를 반환한다. 주로 관리자 대시보드에서 사용한다."""
    return _get_backend().get_recent(limit=limit)


def append_message(
    user_id: str,
    message: dict,
    *,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """대화 이력에 메시지 한 건을 추가한다.

    message는 반드시 role과 content 키를 포함해야 한다.
    message_id가 있으면 중복 저장을 방지한다.
    """
    _get_backend().append(user_id, message, conversation_id=conversation_id, metadata=metadata)


def append_messages(
    user_id: str,
    messages: list[dict],
    *,
    conversation_id: str | None = None,
):
    """대화 이력에 메시지 여러 건을 순서대로 추가한다."""
    for msg in messages:
        _get_backend().append(user_id, msg, conversation_id=conversation_id)


def list_conversations(user_id: str, *, limit: int = 20) -> list[ConversationSummary]:
    """사용자가 참여한 대화를 최근 메시지 시각 기준 내림차순으로 반환한다.

    동일 사용자의 데이터만 노출되며, conversation_id가 다르면 별개의 항목으로 본다.
    """
    return _get_backend().list_conversations(user_id, limit=max(1, limit))


def _make_preview(content: Any) -> str:
    """요약 미리보기용 짧은 문자열을 생성한다."""
    text = "" if content is None else str(content)
    text = text.strip()
    if len(text) <= _PREVIEW_MAX_LENGTH:
        return text
    return text[: _PREVIEW_MAX_LENGTH - 1] + "…"


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

    def list_conversations(self, user_id: str, *, limit: int) -> list[ConversationSummary]:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$sort": {"created_at": -1}},
            {
                "$group": {
                    "_id": "$conversation_id",
                    "last_message_at": {"$first": "$created_at"},
                    "last_message_role": {"$first": "$role"},
                    "last_message_content": {"$first": "$content"},
                    "source": {"$first": "$source"},
                }
            },
            {"$sort": {"last_message_at": -1}},
            {"$limit": limit},
        ]
        summaries: list[ConversationSummary] = []
        for row in self._col.aggregate(pipeline):
            summaries.append(
                ConversationSummary(
                    user_id=user_id,
                    conversation_id=str(row.get("_id") or ""),
                    last_message_at=_format_timestamp(row.get("last_message_at")),
                    last_message_role=str(row.get("last_message_role") or ""),
                    last_message_preview=_make_preview(row.get("last_message_content")),
                    source=row.get("source"),
                )
            )
        return summaries


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
        stored_message["_created_at"] = datetime.now(UTC).isoformat()
        if metadata and metadata.get("source"):
            stored_message["_source"] = metadata["source"]
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

    def list_conversations(self, user_id: str, *, limit: int) -> list[ConversationSummary]:
        prefix = f"{user_id}::"
        records: list[tuple[int, ConversationSummary]] = []
        for store_key, messages in self._store.items():
            if not store_key.startswith(prefix) or not messages:
                continue
            conversation_id = store_key[len(prefix) :]
            last = messages[-1]
            order = int(last.get("_order", 0))
            records.append(
                (
                    order,
                    ConversationSummary(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        last_message_at=str(last.get("_created_at", "")),
                        last_message_role=str(last.get("role", "")),
                        last_message_preview=_make_preview(last.get("content")),
                        source=last.get("_source"),
                    ),
                )
            )
        records.sort(key=lambda record: record[0], reverse=True)
        return [summary for _, summary in records[:limit]]

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

    def list_conversations(self, user_id: str, *, limit: int) -> list[ConversationSummary]:
        summaries: list[ConversationSummary] = []
        for path in self._iter_user_paths(user_id):
            documents = self._read_documents(path)
            if not documents:
                continue
            documents.sort(key=lambda document: document.get("created_at", ""))
            last = documents[-1]
            conversation_id = unquote(path.stem)
            summaries.append(
                ConversationSummary(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    last_message_at=str(last.get("created_at", "")),
                    last_message_role=str(last.get("role", "")),
                    last_message_preview=_make_preview(last.get("content")),
                    source=last.get("source"),
                )
            )
        summaries.sort(key=lambda summary: summary.last_message_at, reverse=True)
        return summaries[:limit]

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
    """conversation_id가 없으면 user_id를 기본 conversation_id로 사용한다."""
    return conversation_id or user_id


def _build_store_key(user_id: str, conversation_id: str | None) -> str:
    """인메모리 백엔드에서 사용하는 복합 키를 생성한다 (형식: user_id::conversation_id)."""
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
    """환경 변수 CONVERSATION_BACKEND 값을 읽어 실제 사용할 백엔드 이름을 결정한다.

    auto 모드에서는 AFM_MONGO_URI 존재 여부에 따라 mongo 또는 memory를 선택한다.
    """
    backend_name = (config.CONVERSATION_BACKEND or "auto").strip().lower()
    if backend_name not in {"auto", "mongo", "local", "memory"}:
        raise ConversationStoreError(f"Unsupported conversation backend: {backend_name}")
    if backend_name == "auto":
        return "mongo" if config.AFM_MONGO_URI else "memory"
    if backend_name == "mongo" and not config.AFM_MONGO_URI:
        raise ConversationStoreError("CONVERSATION_BACKEND=mongo requires AFM_MONGO_URI.")
    return backend_name


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    """document를 JSON 직렬화 후 다시 파싱해 datetime 등 비직렬화 타입을 문자열로 변환한다."""
    return json.loads(json.dumps(document, ensure_ascii=False, default=_json_default))


def _json_default(value: Any) -> str:
    """json.dumps의 default 핸들러 — datetime은 ISO 문자열로, 나머지는 str()로 변환한다."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _format_timestamp(value: Any) -> str:
    """다양한 형태의 시각 값을 ISO 8601 문자열로 정규화한다."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def _encode_path_segment(value: str) -> str:
    """파일 시스템 경로 세그먼트로 사용할 수 있도록 값을 URL 인코딩한다."""
    return quote(value, safe="")


def _strip_message_metadata(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """메시지 목록에서 role·content만 남기고 내부 메타데이터 필드를 제거한다."""
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
