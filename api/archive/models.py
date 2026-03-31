"""아카이브 문서 모델을 정의한다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ArchiveMetadata:
    """아카이브 문서의 메타데이터다."""

    user_id: str
    workflow_id: str
    source: str = "workflow"


@dataclass(slots=True)
class ArchiveDocument:
    """인덱싱할 아카이브 문서다."""

    metadata: ArchiveMetadata
    content: dict[str, Any] = field(default_factory=dict)
