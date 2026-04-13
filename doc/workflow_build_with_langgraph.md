# LangGraph 워크플로 작성 가이드

이 문서는 이 저장소에서 새 워크플로를 LangGraph로 작성할 때 맞춰야 하는 구조와 작업 순서를 설명합니다.

## 기본 원칙

- 이 저장소의 워크플로는 함수 모음이 아니라 상태 기반 그래프로 구성합니다.
- 각 워크플로는 패키지 단위로 분리합니다.
- 운영 반영 전에는 `devtools/workflows/`에서 먼저 구현하고 검증합니다.
- 루트 대화 진입은 `start_chat`이 담당하고, 업무형 워크플로는 서브그래프로 연결합니다.

## 운영 워크플로 패키지의 기본 형태

```text
api/workflows/<workflow_id>/
├── __init__.py
├── lg_graph.py
├── state.py
├── nodes.py          # 필요 시 사용합니다.
├── tools.py          # 필요 시 사용합니다.
└── prompts.py        # 필요 시 사용합니다.
```

실제 최소 계약은 아래 두 가지입니다.

- `__init__.py`에서 `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`을 제공합니다.
- `lg_graph.py`에서 `build_lg_graph()`를 제공합니다.

## `get_workflow_definition()` 계약

레지스트리는 각 패키지의 `get_workflow_definition()`을 읽어 워크플로를 등록합니다.

```python
def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "translator",
        "build_lg_graph": build_lg_graph,
        "state_cls": TranslatorWorkflowState,
        "handoff_keywords": ("번역", "translate"),
    }
```

각 필드의 의미는 아래와 같습니다.

- `workflow_id`는 워크플로 식별자입니다.
- `build_lg_graph`는 LangGraph 빌더 함수입니다.
- `state_cls`는 레지스트리와 기존 계약에서 사용하는 상태 클래스입니다.
- `handoff_keywords`는 `start_chat`에서 이 워크플로로 넘길지 판단하는 기준 키워드입니다.
- `tool_tags`는 관련 도구 범주를 설명할 때 사용합니다.

## 상태 설계 방식

이 저장소에는 상태가 두 층으로 존재합니다.

- `api/workflows/lg_state.py`의 `TypedDict` 계열은 실제 LangGraph 런타임 상태입니다.
- 각 워크플로의 `state.py`는 레지스트리 호환용 상태 클래스입니다.

새 워크플로를 설계할 때는 아래 원칙을 지키는 편이 좋습니다.

- 공통 필드는 `ChatState` 계열에 둡니다.
- 워크플로 전용 슬롯은 해당 워크플로 상태에만 둡니다.
- 사용자에게 다시 물어봐야 하는 값은 명시적인 필드로 보관합니다.

예를 들어 번역 워크플로라면 `source_text`, `target_language`, `last_asked_slot` 같은 필드를 둡니다.

## 그래프 구성 방식

각 워크플로의 `lg_graph.py`에서는 `StateGraph`를 조립합니다.

```python
builder = StateGraph(MyWorkflowState)
builder.add_node("entry", entry_node)
builder.add_node("collect_slot", collect_slot_node)
builder.add_node("complete", complete_node)
builder.set_entry_point("entry")
builder.add_edge("entry", "collect_slot")
builder.add_edge("complete", END)
```

노드 작성 시 기억할 점은 아래와 같습니다.

- 노드는 상태를 읽고 `dict`를 반환해 일부 상태를 갱신합니다.
- 완료 응답은 보통 `messages`에 `AIMessage`를 추가하는 방식으로 돌려줍니다.
- 조건 분기가 필요하면 conditional edge를 사용합니다.
- 여러 턴에 걸친 슬롯 수집은 `interrupt()`와 `Command(resume=...)` 패턴으로 구현합니다.

## 멀티턴 워크플로 작성 방식

이 저장소에서 LangGraph를 쓰는 가장 큰 이유는 멀티턴 업무 플로우를 자연스럽게 다루기 위해서입니다.

예를 들어 아래와 같은 흐름을 구현할 수 있습니다.

1. 원문이 없으면 원문을 요청합니다.
2. 목표 언어가 없으면 목표 언어를 요청합니다.
3. 필요한 값이 모두 모이면 실제 작업을 수행합니다.
4. 응답을 생성하고 종료합니다.

이때 사용자 입력 대기 구간은 `interrupt()`로 멈추고, 다음 메시지는 `resume`으로 이어서 처리합니다.

## 루트 워크플로와의 연결 방식

운영 환경에서는 `start_chat`이 모든 대화의 루트 그래프입니다.

- `api/workflows/start_chat/lg_graph.py`는 handoff 가능한 워크플로를 레지스트리에서 읽습니다.
- `classify_node()`는 메시지와 `handoff_keywords`를 비교해 `detected_intent`를 결정합니다.
- intent가 특정 워크플로와 일치하면 그 서브그래프를 실행합니다.

즉, 새 워크플로를 운영에 붙이려면 서브그래프 형태로 동작할 수 있어야 합니다.

## 도구 연동 방식

워크플로가 외부 도구를 사용해야 하면 보통 `tools.py` 또는 `api/mcp/`와 연결합니다.

- dev 단계에서는 `devtools/mcp/<workflow_id>.py`에 등록 로직을 둡니다.
- 운영 반영 후에는 같은 로직이 `api/mcp/` 아래로 이동합니다.
- `tool_id`는 워크플로별 접두어를 두어 충돌을 피하는 편이 좋습니다.

## 추천 작성 순서

1. `workflow_id`를 정합니다.
2. 어떤 상태 필드가 필요한지 먼저 적습니다.
3. 노드와 분기 조건을 종이에 먼저 그립니다.
4. `lg_graph.py`에서 최소 노드만으로 그래프를 만듭니다.
5. `interrupt/resume`이 필요한 지점을 추가합니다.
6. 도구 연동이 필요하면 `tools.py` 또는 `devtools/mcp/`를 연결합니다.
7. dev runner와 테스트로 검증합니다.

## 테스트 포인트

워크플로를 만들 때는 아래 항목을 반드시 검증하는 편이 좋습니다.

- 첫 입력만으로 완료되는 경로가 정상 동작하는지 확인합니다.
- 누락 슬롯이 있을 때 interrupt가 걸리는지 확인합니다.
- 다음 사용자 입력으로 resume이 정상 동작하는지 확인합니다.
- 레지스트리에서 `workflow_id`를 정상 발견하는지 확인합니다.
- 루트 `start_chat`에서 의도 분기가 기대대로 동작하는지 확인합니다.

## 팀 공통 규칙

- 새 워크플로는 먼저 `devtools/workflows/`에서 시작합니다.
- 패키지 내부 import는 상대 import를 사용합니다.
- 운영 워크플로에 들어갈 키워드는 너무 넓게 잡지 않습니다.
- 상태 필드는 필요한 만큼만 추가하고 의미가 겹치지 않게 유지합니다.
- 그래프 구조가 복잡해지면 `nodes.py`, `prompts.py`, `tools.py`로 분리합니다.

이 규칙을 지키면 워크플로 수가 늘어나도 구조를 비교적 안정적으로 유지할 수 있습니다.
