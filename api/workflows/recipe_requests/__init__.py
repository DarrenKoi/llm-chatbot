"""레시피 요청 워크플로 패키지."""


def get_workflow_definition() -> dict[str, object]:
    """recipe_requests 워크플로 정의를 반환한다."""

    from api.workflows.recipe_requests.graph import build_graph
    from api.workflows.recipe_requests.state import RecipeRequestsWorkflowState

    return {
        "workflow_id": "recipe_requests",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": RecipeRequestsWorkflowState,
        "handoff_keywords": ("recipe", "recipes", "formula", "레시피", "배합", "처방"),
    }
