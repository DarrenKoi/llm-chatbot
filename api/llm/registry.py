"""워크플로와 노드 기준으로 LLM 인스턴스를 조회하는 레지스트리."""

from langchain_openai import ChatOpenAI

from api import config
from api.llm.service import LLMServiceError


def get_llm(*, workflow_id: str, node_id: str | None = None) -> ChatOpenAI:
    """워크플로와 노드 기준 LLM 인스턴스를 반환한다."""

    del workflow_id, node_id

    base_url = config.LLM_BASE_URL.rstrip("/")
    if not base_url:
        raise LLMServiceError("LLM_BASE_URL is not configured.")
    if not config.LLM_MODEL:
        raise LLMServiceError("LLM_MODEL is not configured.")

    return ChatOpenAI(
        base_url=base_url,
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY or "not-needed",
        timeout=config.LLM_TIMEOUT_SECONDS,
    )
