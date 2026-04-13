"""번역 예제 워크플로 전용 LangGraph 상태를 정의한다."""

from api.workflows.lg_state import ChatState


class TranslatorExampleState(ChatState, total=False):
    """번역 요청의 누락 정보를 보완하기 위한 상태다."""

    source_text: str
    source_language: str
    target_language: str
    last_asked_slot: str
    translation_direction: str
    translated: str
    pronunciation_ko: str
    pending_reply: str
    conversation_ended: bool
