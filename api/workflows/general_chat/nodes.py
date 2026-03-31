"""일반 대화 워크플로 노드 스텁을 정의한다."""

from __future__ import annotations

from api.workflows.general_chat.agent.executor import execute_general_chat_plan
from api.workflows.general_chat.agent.planner import plan_general_chat_response
from api.workflows.general_chat.rag.context_builder import build_general_chat_context
from api.workflows.general_chat.rag.retriever import retrieve_general_chat_documents
from api.workflows.general_chat.state import GeneralChatWorkflowState
from api.workflows.models import NodeResult


def entry_node(state: GeneralChatWorkflowState, user_message: str) -> NodeResult:
    """일반 대화 워크플로 진입 노드 스텁이다."""

    del state, user_message
    return NodeResult(action="wait", next_node_id="classify")


def classify_intent_node(state: GeneralChatWorkflowState, user_message: str) -> NodeResult:
    """자유 대화와 업무 워크플로 진입 의도를 구분한다."""

    del user_message
    return NodeResult(
        action="wait",
        next_node_id="retrieve_context",
        data_updates={"detected_intent": state.detected_intent},
    )


def retrieve_context_node(state: GeneralChatWorkflowState, user_message: str) -> NodeResult:
    """일반 질의응답용 검색 컨텍스트를 수집한다."""

    documents = retrieve_general_chat_documents(user_message)
    contexts = build_general_chat_context(documents)
    return NodeResult(
        action="wait",
        next_node_id="plan_response",
        data_updates={"retrieved_contexts": contexts},
    )


def plan_response_node(state: GeneralChatWorkflowState, user_message: str) -> NodeResult:
    """응답 생성 계획을 만든다."""

    plan = plan_general_chat_response(user_message=user_message, state=state)
    return NodeResult(action="wait", next_node_id="generate_reply", data_updates={"agent_plan": plan})


def generate_reply_node(state: GeneralChatWorkflowState, user_message: str) -> NodeResult:
    """실제 응답을 생성한다."""

    reply = execute_general_chat_plan(user_message=user_message, state=state)
    return NodeResult(action="reply", reply=reply, next_node_id="done")
