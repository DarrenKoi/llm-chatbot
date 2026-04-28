"""시작 대화 워크플로 프롬프트 템플릿을 정의한다."""

START_CHAT_CONTEXT_TEMPLATE = """\
아래 참고 자료를 바탕으로 사용자 질문에 답변하세요.

[참고 자료]
{contexts}

[질문]
{question}"""
