"""대화와 워크플로 결과를 아카이브하는 서비스 스텁이다."""

from __future__ import annotations

from api.archive.extractor import extract_archive_document
from api.archive.models import ArchiveDocument
from api.archive.opensearch_client import ArchiveOpenSearchClient
from api.workflows.models import WorkflowState


def archive_workflow_result(*, state: WorkflowState, reply: str) -> ArchiveDocument:
    """워크플로 상태와 응답을 아카이브 문서로 저장한다."""

    document = extract_archive_document(state=state, reply=reply)
    ArchiveOpenSearchClient().index_document(document)
    return document
