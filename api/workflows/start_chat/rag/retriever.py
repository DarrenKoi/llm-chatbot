"""시작 대화용 검색기 스텁을 제공한다."""


def retrieve_start_chat_documents(query: str) -> list[dict[str, str]]:
    """시작 대화에 필요한 문서 후보를 반환한다."""

    return [{"source": "stub", "content": query}]
