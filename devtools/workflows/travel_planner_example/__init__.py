"""여행 계획 예제 워크플로 패키지.

`api/workflows/travel_planner` 구조를 devtools에서도 그대로 익힐 수 있게
거의 동일한 형태로 옮긴 예제다.
"""

from .graph import build_graph
from .state import TravelPlannerExampleState


def get_workflow_definition() -> dict[str, object]:
    """travel_planner_example 워크플로 정의를 반환한다."""

    return {
        "workflow_id": "travel_planner_example",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": TravelPlannerExampleState,
    }
