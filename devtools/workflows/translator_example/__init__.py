"""번역 예제 워크플로 패키지.

`api/workflows/translator` 흐름을 devtools에서 그대로 참고할 수 있게
동일한 파일 분리를 유지한 예제다.
"""

from .graph import build_graph
from .state import TranslatorExampleState


def get_workflow_definition() -> dict[str, object]:
    """translator_example 워크플로 정의를 반환한다."""

    return {
        "workflow_id": "translator_example",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": TranslatorExampleState,
    }
