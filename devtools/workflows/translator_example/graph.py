"""번역 예제 워크플로 그래프를 정의한다."""

from . import nodes
from .tools import register_translator_tools


def build_graph() -> dict[str, object]:
    """입력을 해석하고, 필요한 경우 재질문한 뒤 번역 도구를 호출한다."""

    register_translator_tools()

    return {
        "workflow_id": "translator_example",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_source_text": nodes.collect_source_text_node,
            "collect_target_language": nodes.collect_target_language_node,
            "translate": nodes.translate_node,
        },
        "edges": [
            ("entry", "collect_source_text", "원문 없음"),
            ("entry", "collect_target_language", "언어 없음"),
            ("entry", "translate", "정보 충분"),
            ("collect_source_text", "collect_target_language", "언어 없음"),
            ("collect_source_text", "translate", "정보 충분"),
            ("collect_target_language", "translate"),
            ("translate", "done", "번역 완료"),
        ],
    }
