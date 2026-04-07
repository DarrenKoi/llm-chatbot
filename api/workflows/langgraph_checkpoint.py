"""LangGraph 체크포인터 팩토리와 Mongo 저장소 경계 유틸리티를 제공한다."""

from dataclasses import dataclass

from api import config


@dataclass(frozen=True, slots=True)
class MongoStorageCollections:
    """MongoDB에서 사용하는 컬렉션 이름 묶음."""

    conversation_history: str
    checkpoint: str
    checkpoint_writes: str


def build_thread_id(user_id: str, channel_id: str = "") -> str:
    """사용자 ID와 채널 ID를 결합하여 LangGraph thread_id를 생성한다."""

    if channel_id:
        return f"{user_id}::{channel_id}"
    return user_id


def get_mongo_storage_collections() -> MongoStorageCollections:
    """대화 이력과 LangGraph 체크포인터가 사용할 컬렉션 이름을 반환한다."""

    return MongoStorageCollections(
        conversation_history=config.CONVERSATION_COLLECTION_NAME,
        checkpoint=config.LANGGRAPH_CHECKPOINT_COLLECTION_NAME,
        checkpoint_writes=config.LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME,
    )


def validate_mongo_storage_config() -> MongoStorageCollections:
    """대화 이력과 체크포인터가 서로 다른 Mongo 컬렉션을 사용하도록 검증한다."""

    collections = get_mongo_storage_collections()
    values = (
        collections.conversation_history,
        collections.checkpoint,
        collections.checkpoint_writes,
    )
    normalized = tuple(value.strip() for value in values)
    if not all(normalized):
        raise ValueError("MongoDB collection names must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise ValueError(
            "Conversation history, checkpoint, and checkpoint writes must use different MongoDB collections."
        )
    return collections


def get_checkpointer(*, persistent: bool = True):
    """환경 설정에 따라 적절한 LangGraph 체크포인터를 반환한다.

    ``persistent=False`` 이면 항상 MemorySaver를 사용한다.
    ``persistent=True`` 이고 ``AFM_MONGO_URI``가 설정되면 MongoDBSaver를 사용한다.
    """

    if persistent and config.AFM_MONGO_URI:
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        collections = validate_mongo_storage_config()
        client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return MongoDBSaver(
            client,
            db_name=config.AFM_DB_NAME,
            checkpoint_collection_name=collections.checkpoint,
            writes_collection_name=collections.checkpoint_writes,
            ttl=config.CHECKPOINT_TTL_SECONDS if config.CHECKPOINT_TTL_SECONDS > 0 else None,
        )

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
