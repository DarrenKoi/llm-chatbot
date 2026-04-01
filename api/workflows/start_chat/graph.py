"""시작 대화 워크플로 그래프를 정의한다."""

from api.workflows.start_chat import nodes, routing


def build_graph() -> dict[str, object]:
    """시작 대화 워크플로 그래프 정의를 반환한다."""

    return {
        "workflow_id": "start_chat",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "classify": nodes.classify_intent_node,
            "retrieve_context": nodes.retrieve_context_node,
            "plan_response": nodes.plan_response_node,
            "generate_reply": nodes.generate_reply_node,
        },
        "router": routing.route_next_node,
    }
