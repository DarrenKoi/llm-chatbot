"""시작 대화용 실행기 — LLM을 호출하여 응답을 생성한다."""

import logging

from api.conversation_service import get_history
from api.llm.service import generate_reply
from api.workflows.start_chat.prompts import START_CHAT_CONTEXT_TEMPLATE
from api.workflows.start_chat.state import StartChatWorkflowState

log = logging.getLogger(__name__)


def execute_start_chat_plan(*, user_message: str, state: StartChatWorkflowState) -> str:
    """대화 이력과 RAG 컨텍스트를 바탕으로 LLM 응답을 생성한다."""

    # process_incoming_message()이 워크플로 호출 전에 현재 메시지를 이력에
    # 이미 추가하므로, generate_reply()의 중복 추가를 방지하기 위해 마지막 항목 제외
    history = get_history(state.user_id)
    if history and history[-1].get("role") == "user":
        history = history[:-1]

    contexts = getattr(state, "retrieved_contexts", None) or state.data.get("retrieved_contexts")
    if contexts:
        augmented_message = START_CHAT_CONTEXT_TEMPLATE.format(
            contexts="\n".join(contexts),
            question=user_message,
        )
    else:
        augmented_message = user_message

    return generate_reply(history=history, user_message=augmented_message)
