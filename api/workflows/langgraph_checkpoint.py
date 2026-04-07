"""LangGraph 체크포인터 팩토리와 스레드 ID 유틸리티를 제공한다."""

from api import config


def build_thread_id(user_id: str, channel_id: str = "") -> str:
    """사용자 ID와 채널 ID를 결합하여 LangGraph thread_id를 생성한다."""

    if channel_id:
        return f"{user_id}::{channel_id}"
    return user_id


def get_checkpointer():
    """환경 설정에 따라 적절한 LangGraph 체크포인터를 반환한다.

    AFM_MONGO_URI가 설정되면 MongoDBSaver를, 그렇지 않으면 MemorySaver를 사용한다.
    """

    if config.AFM_MONGO_URI:
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return MongoDBSaver(
            client,
            db_name=config.AFM_DB_NAME,
            checkpoint_collection_name=config.LANGGRAPH_CHECKPOINT_COLLECTION_NAME,
            writes_collection_name=config.LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME,
            ttl=config.CHECKPOINT_TTL_SECONDS if config.CHECKPOINT_TTL_SECONDS > 0 else None,
        )

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
