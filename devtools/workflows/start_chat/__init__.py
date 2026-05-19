"""devtools 전용 start_chat 진입 워크플로 패키지.

운영 ``api/workflows/start_chat/``과 분리된 dev 인프라다. 라우팅 검증만이 목적이며
RAG/file/profile/LLM 노드는 미러링하지 않는다. promote 대상이 아니므로 영구 유지된다.
자세한 정책은 HARNESS.md "devtools start_chat 전용 그래프" 섹션 참고.
"""


def build_lg_graph():
    """dev start_chat LangGraph 빌더를 반환한다."""

    from .lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """dev start_chat 워크플로 정의를 반환한다.

    자기 자신은 핸드오프 대상이 아니므로 handoff_keywords는 비어있다.
    """

    return {
        "workflow_id": "start_chat",
        "build_lg_graph": build_lg_graph,
    }
