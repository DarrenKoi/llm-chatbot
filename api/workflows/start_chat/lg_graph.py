"""시작 대화 LangGraph 워크플로.

메인 대화 진입점이다. 의도 분류 후 일반 대화(RAG + LLM) 또는
자식 워크플로 서브그래프로 분기한다.
"""

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from api.workflows.start_chat.lg_state import StartChatState

log = logging.getLogger(__name__)


def _get_handoff_subgraph_builders() -> dict[str, object]:
    """레지스트리에서 LangGraph 서브그래프를 제공하는 handoff 워크플로를 수집한다."""

    from api.workflows.registry import list_handoff_workflows

    builders: dict[str, object] = {}
    for workflow_def in list_handoff_workflows():
        workflow_id = workflow_def["workflow_id"]
        builder = workflow_def.get("build_lg_graph")
        if callable(builder):
            builders[workflow_id] = builder
    return builders


def entry_node(state: StartChatState) -> dict:
    """프로필을 1회 로딩한다."""

    if state.get("profile_loaded"):
        return {}

    try:
        from api.profile.service import load_user_profile

        profile = load_user_profile(state.get("user_id", ""))
    except Exception:
        log.warning("프로필 로딩 실패 — 빈 프로필로 진행합니다.")
        profile = None

    profile_summary = profile.to_prompt_text() if profile else ""
    profile_source = profile.source if profile else "unavailable"

    return {
        "profile_loaded": profile is not None,
        "profile_source": profile_source,
        "profile_summary": profile_summary,
    }


def classify_node(state: StartChatState) -> dict:
    """사용자 의도를 분류한다."""

    from api.workflows.registry import list_handoff_workflows

    user_message = state.get("user_message", "").strip().lower()
    if not user_message:
        return {"active_workflow": "start_chat"}

    for workflow_def in list_handoff_workflows():
        workflow_id = workflow_def["workflow_id"]
        keywords = workflow_def.get("handoff_keywords", ())
        if any(keyword in user_message for keyword in keywords):
            return {"active_workflow": workflow_id}

    return {"active_workflow": "start_chat"}


def retrieve_context_node(state: StartChatState) -> dict:
    """일반 질의응답용 검색 컨텍스트를 수집한다."""

    from api.workflows.start_chat.rag.context_builder import build_start_chat_context
    from api.workflows.start_chat.rag.retriever import retrieve_start_chat_documents

    user_message = state.get("user_message", "")
    documents = retrieve_start_chat_documents(user_message)
    contexts = build_start_chat_context(documents)
    return {"retrieved_contexts": contexts}


def _build_file_context(user_id: str) -> str:
    """사용자 업로드 파일 목록을 LLM 컨텍스트 문자열로 반환한다."""

    from api.file_delivery import list_files_for_user

    files = list_files_for_user(user_id=user_id, limit=20)
    if not files:
        return ""

    lines: list[str] = []
    for f in files:
        name = f.get("original_filename") or f.get("title") or f.get("file_id", "")
        url = f.get("file_url", "")
        source = f.get("source", "")
        created = (f.get("created_at") or "")[:10]
        tag = f" [{source}]" if source else ""
        lines.append(f"- {name}{tag} ({created}): {url}")

    return "[사용자 파일]\n" + "\n".join(lines)


def generate_reply_node(state: StartChatState) -> dict:
    """LLM을 호출하여 ReplyIntent를 받고, 평문/구조 블록을 함께 상태에 적재한다."""

    from api.conversation_service import get_history
    from api.cube.intents import TextIntent
    from api.llm.service import generate_reply_intent
    from api.workflows.start_chat.prompts import START_CHAT_CONTEXT_TEMPLATE

    user_id = state.get("user_id", "")
    channel_id = state.get("channel_id", "")
    user_message = state.get("user_message", "")
    contexts = list(state.get("retrieved_contexts", []))
    profile_summary = state.get("profile_summary", "")

    file_context = ""
    if user_id:
        try:
            file_context = _build_file_context(user_id)
        except Exception:
            log.exception("Failed to load file-delivery context for start_chat.")
    if file_context:
        contexts.append(file_context)

    history = get_history(user_id, conversation_id=channel_id or None)
    if history and history[-1].get("role") == "user":
        history = history[:-1]

    if contexts:
        augmented_message = START_CHAT_CONTEXT_TEMPLATE.format(
            contexts="\n".join(contexts),
            question=user_message,
        )
    else:
        augmented_message = user_message

    reply_intent = generate_reply_intent(
        history=history,
        user_message=augmented_message,
        user_profile_text=profile_summary,
    )

    text_fallback = "\n\n".join(block.text for block in reply_intent.blocks if isinstance(block, TextIntent)).strip()
    if not text_fallback:
        text_fallback = "[start_chat] 처리 완료."

    has_structured = any(not isinstance(block, TextIntent) for block in reply_intent.blocks)
    return {
        "messages": [AIMessage(content=text_fallback)],
        "reply_intents": list(reply_intent.blocks) if has_structured else None,
    }


def _route_after_classify(state: StartChatState) -> str:
    """classify 후 다음 노드를 결정한다."""

    intent = state.get("active_workflow", "start_chat")
    if intent in _get_handoff_subgraph_builders():
        return intent
    return "retrieve_context"


def build_lg_graph() -> StateGraph:
    """시작 대화 워크플로 LangGraph StateGraph 빌더를 반환한다.

    자식 워크플로(translator)는 서브그래프로 포함된다.
    """

    handoff_subgraphs = _get_handoff_subgraph_builders()
    builder = StateGraph(StartChatState)

    # 메인 노드
    builder.add_node("entry", entry_node)
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("generate_reply", generate_reply_node)

    # 자식 워크플로 서브그래프
    for workflow_id, subgraph_builder in handoff_subgraphs.items():
        builder.add_node(workflow_id, subgraph_builder().compile())

    # 엣지
    builder.set_entry_point("entry")
    builder.add_edge("entry", "classify")
    builder.add_conditional_edges("classify", _route_after_classify)
    builder.add_edge("retrieve_context", "generate_reply")
    builder.add_edge("generate_reply", END)
    for workflow_id in handoff_subgraphs:
        builder.add_edge(workflow_id, END)

    return builder
