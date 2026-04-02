"""샘플 번역 워크플로 그래프를 정의한다."""

from api.workflows.sample import nodes


def build_graph() -> dict[str, object]:
    """입력을 해석하고, 필요한 경우 재질문한 뒤 번역 도구를 호출한다."""

    return {
        "workflow_id": "sample",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_source_text": nodes.collect_source_text_node,
            "collect_target_language": nodes.collect_target_language_node,
            "translate": nodes.translate_node,
        },
    }
