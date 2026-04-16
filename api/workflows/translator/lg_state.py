"""번역 워크플로 전용 상태 정의."""

from api.workflows.lg_state import ChatState


class TranslatorState(ChatState, total=False):
    """번역 워크플로 전용 상태."""

    source_text: str
    source_language: str
    target_language: str
    last_asked_slot: str
    translation_direction: str
    translated: str
    pronunciation_ko: str
