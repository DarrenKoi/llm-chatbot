"""시작 대화 워크플로 라우팅 규칙을 정의한다."""

from api.workflows.models import NodeResult
from api.workflows.registry import list_handoff_workflows
from api.workflows.start_chat.state import StartChatWorkflowState


def route_next_node(state: StartChatWorkflowState, result: NodeResult) -> str | None:
    """노드 결과에 따라 다음 노드를 결정한다."""

    del state
    return result.next_node_id


def detect_intent(state: StartChatWorkflowState, user_message: str) -> str:
    """현재 메시지와 상태를 바탕으로 다음 의도를 추정한다."""

    normalized = user_message.strip().lower()
    if not normalized:
        return getattr(state, "detected_intent", state.data.get("detected_intent", "start_chat"))

    for workflow_def in list_handoff_workflows():
        workflow_id = workflow_def["workflow_id"]
        keywords = workflow_def.get("handoff_keywords", ())
        if any(keyword in normalized for keyword in keywords):
            return workflow_id

    return "start_chat"


def determine_handoff_workflow(state: StartChatWorkflowState) -> str | None:
    """시작 대화에서 다른 업무 워크플로로 넘길 대상을 판단한다."""

    intent = getattr(state, "detected_intent", state.data.get("detected_intent", ""))
    handoff_workflow_ids = {
        workflow_def["workflow_id"]
        for workflow_def in list_handoff_workflows()
    }
    if intent in handoff_workflow_ids:
        return intent
    return None
