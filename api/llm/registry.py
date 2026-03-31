"""워크플로와 노드 기준으로 LLM 구성을 조회하는 레지스트리 스텁이다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LLMConfig:
    """LLM 선택에 필요한 최소 설정값이다."""

    model_name: str
    temperature: float = 0.0
    options: dict[str, Any] = field(default_factory=dict)


_DEFAULT_CONFIG = LLMConfig(model_name="gpt-4.1-mini")


def get_llm_config(*, workflow_id: str, node_id: str | None = None) -> LLMConfig:
    """워크플로와 노드 기준 기본 LLM 구성을 반환한다."""

    del workflow_id, node_id
    return _DEFAULT_CONFIG


def get_llm_client(*, workflow_id: str, node_id: str | None = None) -> Any:
    """실제 LLM 클라이언트 생성 위치를 위한 스텁이다."""

    return {"config": get_llm_config(workflow_id=workflow_id, node_id=node_id)}
