"""대화와 워크플로 결과에서 아카이브 문서를 추출한다."""

from __future__ import annotations

from api.archive.models import ArchiveDocument, ArchiveMetadata
from api.workflows.models import WorkflowState


def extract_archive_document(*, state: WorkflowState, reply: str) -> ArchiveDocument:
    """워크플로 상태와 응답을 아카이브 문서로 변환한다."""

    return ArchiveDocument(
        metadata=ArchiveMetadata(user_id=state.user_id, workflow_id=state.workflow_id),
        content={
            "node_id": state.node_id,
            "status": state.status,
            "data": state.data,
            "reply": reply,
        },
    )
