"""OpenSearch 연동 클라이언트 스텁을 제공한다."""

from __future__ import annotations

from api.archive.models import ArchiveDocument


class ArchiveOpenSearchClient:
    """아카이브 문서 인덱싱을 위한 얇은 클라이언트 스텁이다."""

    def index_document(self, document: ArchiveDocument) -> dict[str, str]:
        """문서를 인덱싱하고 최소 응답을 반환한다."""

        return {
            "result": "stubbed",
            "workflow_id": document.metadata.workflow_id,
            "user_id": document.metadata.user_id,
        }
