"""시작 대화 워크플로 프롬프트 템플릿을 정의한다."""

START_CHAT_SYSTEM_PROMPT = """자유 대화와 일반 질의응답을 담당한다."""
START_CHAT_ROUTING_PROMPT = """업무 요청이면 적절한 workflow id를 추론한다."""
START_CHAT_RAG_PROMPT = """검색된 사내 문맥을 답변에 자연스럽게 녹여낸다."""

START_CHAT_CONTEXT_TEMPLATE = """\
아래 참고 자료를 바탕으로 사용자 질문에 답변하세요.

[참고 자료]
{contexts}

[질문]
{question}"""
