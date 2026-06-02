import json
import time
from dataclasses import asdict
from typing import Any

from api import config
from api.cube.models import CubeIncomingMessage, CubeQueuedMessage


class CubeQueueError(RuntimeError):
    """Raised when the Redis-backed Cube queue is unavailable."""


_backend: "_RedisCubeQueueBackend | None" = None


def enqueue_incoming_message(incoming: CubeIncomingMessage) -> bool:
    return _get_backend().enqueue_unique(incoming)


def dequeue_queued_message(*, timeout_seconds: int | None = None) -> CubeQueuedMessage | None:
    return _get_backend().dequeue(timeout_seconds=timeout_seconds)


def acknowledge_queued_message(queued_message: CubeQueuedMessage) -> None:
    _get_backend().acknowledge(queued_message)


def requeue_queued_message(queued_message: CubeQueuedMessage, *, next_attempt: int) -> CubeQueuedMessage:
    # enqueued_at을 유지해 재시도가 메시지 나이 시계를 초기화하지 않도록 한다.
    replacement = CubeQueuedMessage(
        incoming=queued_message.incoming,
        attempt=next_attempt,
        enqueued_at=queued_message.enqueued_at,
    )
    _get_backend().requeue(queued_message, replacement)
    return replacement


def recover_processing_messages() -> int:
    return _get_backend().recover_processing_messages()


def mark_message_processed(incoming: CubeIncomingMessage) -> None:
    _get_backend().mark_processed(incoming)


def is_message_processed(incoming: CubeIncomingMessage) -> bool:
    return _get_backend().is_processed(incoming)


def _get_backend() -> "_RedisCubeQueueBackend":
    global _backend
    if _backend is not None:
        return _backend

    redis_url = config.CUBE_QUEUE_REDIS_URL
    if not redis_url:
        raise CubeQueueError("REDIS_URL is not configured.")

    try:
        import redis

        block_timeout = config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS
        socket_timeout = block_timeout + 5
        client = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=socket_timeout)
        client.ping()
    except Exception as exc:
        raise CubeQueueError(f"Cube queue Redis connection failed: {exc}") from exc

    _backend = _RedisCubeQueueBackend(client)
    return _backend


class _RedisCubeQueueBackend:
    _ENQUEUE_SCRIPT = """
local ready_queue = KEYS[1]
local dedup_key = KEYS[2]
local payload = ARGV[1]
local dedup_ttl = tonumber(ARGV[2])

if dedup_key == "" then
    redis.call("LPUSH", ready_queue, payload)
    return 1
end

local reserved = redis.call("SET", dedup_key, "1", "NX", "EX", dedup_ttl)
if not reserved then
    return 0
end

redis.call("LPUSH", ready_queue, payload)
return 1
"""

    def __init__(self, client: Any):
        self._r = client

    def enqueue_unique(self, incoming: CubeIncomingMessage) -> bool:
        queued_message = CubeQueuedMessage(incoming=incoming, enqueued_at=time.time())
        dedup_key = self._dedup_key(incoming) or ""
        raw = self._serialize_message(queued_message)
        try:
            queued = self._r.eval(
                self._ENQUEUE_SCRIPT,
                2,
                config.CUBE_QUEUE_NAME,
                dedup_key,
                raw,
                config.CUBE_MESSAGE_DEDUP_TTL_SECONDS,
            )
        except Exception as exc:
            raise CubeQueueError(f"Cube queue enqueue failed: {exc}") from exc
        return bool(queued)

    def dequeue(self, *, timeout_seconds: int | None = None) -> CubeQueuedMessage | None:
        timeout_seconds = config.CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        try:
            if timeout_seconds <= 0:
                raw = self._r.rpoplpush(config.CUBE_QUEUE_NAME, config.CUBE_QUEUE_PROCESSING_NAME)
            else:
                raw = self._r.brpoplpush(
                    config.CUBE_QUEUE_NAME,
                    config.CUBE_QUEUE_PROCESSING_NAME,
                    timeout_seconds,
                )
        except Exception as exc:
            raise CubeQueueError(f"Cube queue dequeue failed: {exc}") from exc

        if raw is None:
            return None
        return self._deserialize_message(raw)

    def acknowledge(self, queued_message: CubeQueuedMessage) -> None:
        raw = self._removal_payload(queued_message)
        try:
            self._r.lrem(config.CUBE_QUEUE_PROCESSING_NAME, 1, raw)
        except Exception as exc:
            raise CubeQueueError(f"Cube queue acknowledge failed: {exc}") from exc

    def requeue(self, current_message: CubeQueuedMessage, replacement_message: CubeQueuedMessage) -> None:
        current_raw = self._removal_payload(current_message)
        replacement_raw = self._serialize_message(replacement_message)
        try:
            pipeline = self._r.pipeline()
            pipeline.lrem(config.CUBE_QUEUE_PROCESSING_NAME, 1, current_raw)
            pipeline.lpush(config.CUBE_QUEUE_NAME, replacement_raw)
            pipeline.execute()
        except Exception as exc:
            raise CubeQueueError(f"Cube queue requeue failed: {exc}") from exc

    def recover_processing_messages(self) -> int:
        recovered = 0
        try:
            while True:
                moved = self._r.rpoplpush(config.CUBE_QUEUE_PROCESSING_NAME, config.CUBE_QUEUE_NAME)
                if moved is None:
                    break
                recovered += 1
        except Exception as exc:
            raise CubeQueueError(f"Cube queue recovery failed: {exc}") from exc
        return recovered

    def mark_processed(self, incoming: CubeIncomingMessage) -> None:
        # 처리 완료 멱등성 마커. message_id가 없으면 기록하지 않는다(중복 식별 불가).
        key = self._processed_key(incoming)
        if key is None:
            return
        # ex는 1 이상이어야 한다. 설정값이 0/음수여도(오설정) 마커가 조용히 비활성화되지 않도록 하한을 둔다.
        ttl = max(1, config.CUBE_MESSAGE_PROCESSED_TTL_SECONDS)
        try:
            self._r.set(key, "1", ex=ttl)
        except Exception as exc:
            raise CubeQueueError(f"Cube queue mark-processed failed: {exc}") from exc

    def is_processed(self, incoming: CubeIncomingMessage) -> bool:
        key = self._processed_key(incoming)
        if key is None:
            return False
        try:
            return bool(self._r.exists(key))
        except Exception as exc:
            raise CubeQueueError(f"Cube queue processed-check failed: {exc}") from exc

    @staticmethod
    def _removal_payload(queued_message: CubeQueuedMessage) -> str:
        # 처리 큐에서 LREM으로 제거할 때는 큐에 들어있는 원본 문자열과 정확히 일치해야 한다.
        # dequeue된 메시지는 원본(raw)을 보존하므로 직렬화 형식이 바뀌어도 안전하게 제거된다.
        if queued_message.raw is not None:
            return queued_message.raw
        return _RedisCubeQueueBackend._serialize_message(queued_message)

    @staticmethod
    def _serialize_message(queued_message: CubeQueuedMessage) -> str:
        return json.dumps(
            {
                "incoming": asdict(queued_message.incoming),
                "attempt": queued_message.attempt,
                "enqueued_at": queued_message.enqueued_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize_message(raw: bytes | str) -> CubeQueuedMessage:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        raw_payload = raw

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CubeQueueError("Cube queue payload is not valid JSON.") from exc

        if not isinstance(data, dict):
            raise CubeQueueError("Cube queue payload must be a JSON object.")

        incoming_data = data.get("incoming")
        if not isinstance(incoming_data, dict):
            raise CubeQueueError("Cube queue payload does not contain an incoming message.")

        try:
            incoming = CubeIncomingMessage(
                user_id=str(incoming_data["user_id"]),
                user_name=str(incoming_data["user_name"]),
                channel_id=str(incoming_data["channel_id"]),
                message_id=str(incoming_data["message_id"]),
                message=str(incoming_data["message"]),
            )
            attempt = int(data.get("attempt", 0))
            enqueued_at_raw = data.get("enqueued_at")
            enqueued_at = float(enqueued_at_raw) if enqueued_at_raw is not None else None
        except (KeyError, TypeError, ValueError) as exc:
            raise CubeQueueError("Cube queue payload is malformed.") from exc

        return CubeQueuedMessage(incoming=incoming, attempt=attempt, enqueued_at=enqueued_at, raw=raw_payload)

    @staticmethod
    def _dedup_key(incoming: CubeIncomingMessage) -> str | None:
        if not incoming.message_id:
            return None
        return f"{config.CUBE_QUEUE_NAME}:dedup:{incoming.user_id}:{incoming.message_id}"

    @staticmethod
    def _processed_key(incoming: CubeIncomingMessage) -> str | None:
        if not incoming.message_id:
            return None
        return f"{config.CUBE_QUEUE_NAME}:done:{incoming.user_id}:{incoming.message_id}"
