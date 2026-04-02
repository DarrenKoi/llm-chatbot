"""번역 서비스 워크플로 전용 상태를 정의한다."""

from dataclasses import dataclass

from api.workflows.models import WorkflowState


@dataclass
class TranslatorWorkflowState(WorkflowState):
    """번역 요청의 누락 정보를 보완하기 위한 상태다."""

    source_text: str = ""
    source_language: str = ""
    target_language: str = ""
    last_asked_slot: str = ""
