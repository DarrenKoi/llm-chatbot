"""시작 대화 워크플로 노드를 정의한다."""

from api.profile.service import load_user_profile
from api.workflows.start_chat.agent.executor import execute_start_chat_plan
from api.workflows.start_chat.agent.planner import plan_start_chat_response
from api.workflows.start_chat.rag.context_builder import build_start_chat_context
from api.workflows.start_chat.rag.retriever import retrieve_start_chat_documents
from api.workflows.start_chat.routing import detect_intent, determine_handoff_workflow
from api.workflows.start_chat.state import StartChatWorkflowState
from api.workflows.models import NodeResult


def entry_node(state: StartChatWorkflowState, user_message: str) -> NodeResult:
    """시작 대화 워크플로 진입 시 프로필을 1회 로딩한다."""

    del user_message

    if state.profile_loaded:
        return NodeResult(action="resume", next_node_id="classify")

    profile = load_user_profile(state.user_id)
    profile_summary = profile.to_prompt_text() if profile else ""
    profile_source = profile.source if profile else "unavailable"

    return NodeResult(
        action="resume",
        next_node_id="classify",
        data_updates={
            "profile_loaded": profile is not None,
            "profile_source": profile_source,
            "profile_summary": profile_summary,
        },
    )


def classify_intent_node(state: StartChatWorkflowState, user_message: str) -> NodeResult:
    """사용자 의도를 분류하고 일반 대화 또는 전문 워크플로로 분기한다."""

    intent = detect_intent(state, user_message)
    state.detected_intent = intent

    handoff_target = determine_handoff_workflow(state)
    if handoff_target:
        return NodeResult(
            action="handoff",
            next_workflow_id=handoff_target,
            data_updates={"detected_intent": intent},
        )
    return NodeResult(
        action="resume",
        next_node_id="retrieve_context",
        data_updates={"detected_intent": intent},
    )


def retrieve_context_node(state: StartChatWorkflowState, user_message: str) -> NodeResult:
    """일반 질의응답용 검색 컨텍스트를 수집한다."""

    del state
    documents = retrieve_start_chat_documents(user_message)
    contexts = build_start_chat_context(documents)
    return NodeResult(
        action="resume",
        next_node_id="plan_response",
        data_updates={"retrieved_contexts": contexts},
    )


def plan_response_node(state: StartChatWorkflowState, user_message: str) -> NodeResult:
    """응답 생성 계획을 만든다."""

    plan = plan_start_chat_response(user_message=user_message, state=state)
    return NodeResult(action="resume", next_node_id="generate_reply", data_updates={"agent_plan": plan})


def generate_reply_node(state: StartChatWorkflowState, user_message: str) -> NodeResult:
    """실제 응답을 생성한다."""

    reply = execute_start_chat_plan(user_message=user_message, state=state)
    return NodeResult(action="complete", reply=reply)
