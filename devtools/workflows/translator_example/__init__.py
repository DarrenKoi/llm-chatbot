"""번역 예제 워크플로 패키지.

`api/workflows/translator` 흐름을 devtools에서 그대로 참고할 수 있게
동일한 파일 분리를 유지한 예제다.
"""


def build_lg_graph():
    """translator_example LangGraph 빌더를 반환한다."""

    from .lg_graph import build_lg_graph as builder
    from .tools import register_translator_tools

    register_translator_tools()
    return builder()


def get_workflow_definition() -> dict[str, object]:
    """translator_example 워크플로 정의를 반환한다."""

    return {
        "workflow_id": "translator_example",
        "build_lg_graph": build_lg_graph,
    }
