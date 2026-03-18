import json
from collections import OrderedDict

from api import config

_backend = None


def _redis_urls() -> list[str]:
    urls: list[str] = []
    if config.REDIS_URL:
        urls.append(config.REDIS_URL)
    if config.REDIS_FALLBACK_URL and config.REDIS_FALLBACK_URL != config.REDIS_URL:
        urls.append(config.REDIS_FALLBACK_URL)
    return urls


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    redis_urls = _redis_urls()
    if redis_urls:
        import redis
        for redis_url in redis_urls:
            try:
                client = redis.from_url(redis_url)
                client.ping()
                _backend = _RedisBackend(client)
                break
            except Exception:
                continue
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


class _RedisBackend:
    def __init__(self, client):
        self._r = client

    def _key(self, user_id: str) -> str:
        return f"chat:{user_id}"

    def get(self, user_id: str) -> list[dict]:
        data = self._r.get(self._key(user_id))
        if not data:
            return []
        return json.loads(data)

    def append(self, user_id: str, message: dict):
        history = self.get(user_id)
        history.append(message)
        history = history[-config.CONVERSATION_MAX_MESSAGES:]
        self._r.set(
            self._key(user_id),
            json.dumps(history, ensure_ascii=False),
            ex=config.CONVERSATION_TTL_SECONDS,
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
