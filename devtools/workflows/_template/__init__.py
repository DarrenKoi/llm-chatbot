"""__WORKFLOW_ID__ 워크플로 패키지.

새 워크플로를 scaffold할 때 이 파일의 __WORKFLOW_ID__와
__STATE_CLASS__ 플레이스홀더가 실제 값으로 치환된다.
"""

from .graph import build_graph
from .state import __STATE_CLASS__


def get_workflow_definition() -> dict[str, object]:
    """워크플로 정의를 반환한다."""

    return {
        "workflow_id": "__WORKFLOW_ID__",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": __STATE_CLASS__,
        "handoff_keywords": (),
    }
