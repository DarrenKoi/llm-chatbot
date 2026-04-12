"""프로젝트 전체에서 공유하는 MongoDB 클라이언트 팩토리.

conversation_service와 langgraph_checkpoint 등이 동일한 클라이언트를 재사용하여
uWSGI 워커당 하나의 커넥션 풀만 유지한다.
"""

import threading

from api import config

_client = None
_lock = threading.Lock()


def get_mongo_client():
    """캐싱된 MongoClient 인스턴스를 반환한다.

    첫 호출 시 연결을 생성하고 ping으로 도달 가능 여부를 검증한다.
    이후 호출에서는 동일한 클라이언트를 재사용한다.

    Raises:
        ValueError: AFM_MONGO_URI가 비어 있을 때.
        ConnectionFailure: MongoDB에 연결할 수 없을 때.
    """

    global _client

    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        if not config.AFM_MONGO_URI:
            raise ValueError("AFM_MONGO_URI is not configured.")

        from pymongo import MongoClient

        client = MongoClient(config.AFM_MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        _client = client

    return _client


def _reset_client():
    """테스트 전용: 싱글턴 상태를 초기화한다."""

    global _client
    _client = None
