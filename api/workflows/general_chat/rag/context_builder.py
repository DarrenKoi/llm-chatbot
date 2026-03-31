"""일반 대화용 검색 결과를 컨텍스트로 정리한다."""

from __future__ import annotations


def build_general_chat_context(documents: list[dict[str, str]]) -> list[str]:
    """검색 결과를 LLM 입력용 문자열 컨텍스트로 변환한다."""

    return [document["content"] for document in documents]
