---
tags: [concept, workflow, state, langgraph]
level: beginner
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/workflow_상태_관리_가이드.md
  - api/workflows/lg_state.py
---

# 워크플로 상태 관리 (Workflow State Management)

> 공유 `ChatState` 는 한 곳에만 두고, 워크플로 전용 상태는 각 패키지 안의 `lg_state.py` 에 가둔다.

## 왜 필요한가? (Why)

- 모든 워크플로 상태를 `api/workflows/lg_state.py` 한 파일에 모았더니 새 워크플로 추가 때마다 머지 충돌이 생겼다.
- 어떤 상태가 어떤 워크플로 소유인지 파일 하나로는 보이지 않는다 — 자립성이 떨어졌다.
- Bitbucket 동기화 시 동료가 추가한 상태 정의가 덮어씌워질 위험이 있었다.
- 비슷한 다른 개념과의 차이: dataclass 기반 `WorkflowState` (devtools/legacy 호환) 와 LangGraph 런타임 상태 `TypedDict` 가 별도로 존재한다 — 이 페이지는 후자(런타임 상태)를 다룬다.

## 핵심 개념 (What)

### 정의

워크플로 상태는 두 층으로 나뉜다 (`raw/learning-logs/workflow_상태_관리_가이드.md` §핵심 원칙):

1. **공유 기본 상태** — `api/workflows/lg_state.py` 의 `ChatState`. 모든 워크플로 공통.
2. **워크플로 전용 상태** — `api/workflows/<workflow_id>/lg_state.py` 의 `<Name>State`. `ChatState` 를 상속.

### 관련 용어

- `ChatState`: 공유 `TypedDict(total=False)`. 6 개 공통 필드 (코드 확인: `api/workflows/lg_state.py:12-20`).
- `total=False`: `TypedDict` 의 모든 필드를 선택적(optional)으로 만든다. 슬롯필링에서 "아직 채워지지 않은 슬롯"을 자연스럽게 비워 두기 위함.
- `add_messages`: `messages` 필드의 reducer. 새 메시지가 와도 기존 리스트를 덮지 않고 누적.

### 시각화 / 모델

`ChatState` 의 실제 필드 (코드 기준 — raw 메모의 표와는 일부 다름):

| 필드 | 타입 | 용도 |
|------|------|------|
| `messages` | `Annotated[list, add_messages]` | LangGraph 메시지 히스토리 누적 |
| `user_id` | `str` | 사용자 식별자 |
| `channel_id` | `str` | 채널 식별자 |
| `user_message` | `str` | 현재 턴의 사용자 메시지 |
| `conversation_ended` | `bool` | 대화 종료 플래그 |
| `pending_reply` | `str` | 대기 중인 응답 (collect 노드 등에서 prompt 보관) |

> Conflict: `raw/learning-logs/workflow_상태_관리_가이드.md` §`ChatState 참고` 표에는 위 6 개와 같은 목록이 있지만, 일부 환경/시점에 따라 추가 필드(예: 라우팅 메타)가 더 있을 수 있다. 합성 시점(2026-05-01) `api/workflows/lg_state.py:12-20` 코드와 raw 표는 일치한다. 향후 코드가 변경되면 이 표를 동기화할 것.

```text
api/workflows/
├── lg_state.py                  ← ChatState (공유 기본)
├── translator/
│   ├── __init__.py
│   ├── lg_state.py              ← TranslatorState(ChatState, total=False)
│   └── lg_graph.py
└── start_chat/
    ├── __init__.py
    ├── lg_state.py              ← StartChatState(ChatState, total=False)
    └── lg_graph.py
```

## 어떻게 사용하는가? (How)

### 최소 예제

```python
# api/workflows/my_workflow/lg_state.py

from api.workflows.lg_state import ChatState


class MyWorkflowState(ChatState, total=False):
    """my_workflow 전용 상태."""

    source_text: str
    target_language: str
    last_asked_slot: str
```

```python
# api/workflows/my_workflow/lg_graph.py

from api.workflows.my_workflow.lg_state import MyWorkflowState  # 절대 경로


def build_lg_graph():
    builder = StateGraph(MyWorkflowState)
    ...
```

### 실무 패턴

- **공유 필드 최소화, 로컬 필드 풍부**: `ChatState` 에는 진짜 모든 워크플로가 공유할 필드만. 워크플로 고유 슬롯은 패키지 내부.
- **여러 턴에서 다시 참조할 값만 상태에 둠**: 한 노드 안에서만 쓰고 버릴 값은 로컬 변수.
- **devtools 단계에서도 같은 패턴**: `devtools/workflows/<workflow_id>/lg_state.py` 에 정의하고 `promote` 가 `api/` 로 옮긴다.
- **상태 import 는 절대 경로**: `lg_graph.py` 는 `from api.workflows.<workflow_id>.lg_state import ...` — `promote` 스크립트가 `devtools.mcp.` → `api.mcp.` 만 치환하므로 다른 import 는 처음부터 운영 경로 기준으로 작성.

### 주의사항 / 함정

- **`ChatState` 직접 수정 금지**: 모든 워크플로에 영향이 간다. 변경이 필요하면 팀 합의.
- **`total=False` 유지**: 슬롯필링 패턴이 "비어있는 필드"를 라우팅 단서로 쓰기 때문. `total=True` 로 바꾸면 워크플로 시작 시 모든 필드를 채우라고 강제하게 되어 패턴 자체가 깨진다.
- **같은 의미의 필드 중복 금지**: `text`, `input_text`, `source_text` 처럼 의미가 겹치는 슬롯을 늘리지 말 것.
- **공유 파일에 워크플로별 상태를 추가하는 실수**: 공유 `lg_state.py` 에 `MyWorkflowState` 를 정의하면 자립성이 깨지고 동기화 시 덮어쓰기 위험이 다시 생긴다.
- **상태 전체를 반환하지 말 것**: 노드 함수는 변경할 필드만 dict 로 반환 — LangGraph 가 머지한다 (`raw/learning-logs/workflow_추가_가이드.md` §5).

## 참고 자료 (References)

- 원본 메모: [../../raw/learning-logs/workflow_상태_관리_가이드.md](../../raw/learning-logs/workflow_상태_관리_가이드.md)
- 관련 개념:
  - [workflow-registration.md](workflow-registration.md) — 등록 계약
  - [workflow-authoring.md](workflow-authoring.md) — 새 워크플로 만드는 절차
  - [workflow-runtime-structure.md](workflow-runtime-structure.md) — 런타임 구조 전반
- 코드 경로:
  - `api/workflows/lg_state.py`
  - `api/workflows/translator/lg_state.py`
  - `api/workflows/start_chat/lg_state.py`
- 외부 문서: LangGraph State 와 reducer — <https://docs.langchain.com/oss/python/langgraph/use-graph-api>
