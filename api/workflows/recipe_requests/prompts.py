"""레시피 요청 워크플로 프롬프트 템플릿 자리다."""

RECIPE_REQUESTS_SYSTEM_PROMPT = """레시피 요청에 필요한 정보를 단계적으로 수집한다."""
RECIPE_SLOT_FILLING_PROMPT = """누락된 입력을 한 번에 하나씩 질문한다."""
RECIPE_CONFIRM_PROMPT = """수집된 정보를 요약하고 제출 전 확인한다."""
