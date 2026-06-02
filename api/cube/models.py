from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CubeIncomingMessage:
    user_id: str
    user_name: str
    channel_id: str
    message_id: str
    message: str


@dataclass(frozen=True, slots=True)
class CubeHandledMessage:
    user_id: str
    user_name: str
    channel_id: str
    message_id: str
    user_message: str
    llm_reply: str


@dataclass(frozen=True, slots=True)
class CubeAcceptedMessage:
    user_id: str
    user_name: str
    channel_id: str
    message_id: str
    status: str


@dataclass(frozen=True, slots=True)
class CubeQueuedMessage:
    incoming: CubeIncomingMessage
    attempt: int = 0
    # enqueue 시각(epoch seconds). 최초 enqueue 때 설정되고 재시도(requeue) 시에도 유지되어
    # 메시지 나이 측정 기준이 된다. 구버전 페이로드에는 없을 수 있어 None을 허용한다.
    enqueued_at: float | None = None
    # 큐에서 읽어온 원본 페이로드 문자열. LREM 정확 일치 제거에 사용하며 직렬화/동등성 비교에서 제외한다.
    raw: str | None = field(default=None, compare=False)
