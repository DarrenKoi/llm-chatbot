# 워크플로 상태(State) 관리 가이드

이 문서는 워크플로별 LangGraph 상태 클래스를 어디에, 어떻게 정의해야 하는지 팀원용으로 정리한 안내서입니다.

## 핵심 원칙

- 공유 기본 상태 `ChatState`는 `api/workflows/lg_state.py`에 한 번만 정의합니다.
- 워크플로 전용 상태는 **각 워크플로 패키지 안의 `lg_state.py`**에 정의합니다.
- 하나의 공유 파일에 모든 워크플로 상태를 몰아두지 않습니다.

## 변경 이유

기존에는 `api/workflows/lg_state.py` 하나에 `ChatState`, `TranslatorState`, `TravelPlannerState` 등 모든 상태 클래스가 함께 있었습니다.

이 방식의 문제점:

- 새 워크플로를 추가할 때마다 공유 파일을 수정해야 하므로 **머지 충돌**이 잦았습니다.
- 어떤 상태가 어떤 워크플로에 속하는지 파일 하나만 보고는 파악이 어려웠습니다.
- Bitbucket 동기화 시 팀원이 추가한 워크플로 상태까지 덮어씌워질 위험이 있었습니다.
- 워크플로 패키지의 자립성(self-contained)이 떨어졌습니다.

## 현재 구조

```text
api/workflows/
├── lg_state.py              ← ChatState만 정의 (공유 기본 상태)
├── translator/
│   ├── __init__.py
│   ├── lg_state.py          ← TranslatorState 정의
│   └── lg_graph.py
├── travel_planner/
│   ├── __init__.py
│   ├── lg_state.py          ← TravelPlannerState 정의
│   └── lg_graph.py
└── start_chat/
    ├── __init__.py
    ├── lg_state.py           ← StartChatState 정의
    └── lg_graph.py
```

## 새 워크플로 상태를 추가하는 방법

### 1단계. 공유 기본 상태를 상속합니다

모든 워크플로 상태는 `ChatState`를 상속해야 합니다. `ChatState`에는 `messages`, `user_id`, `channel_id` 등 공통 필드가 들어 있습니다.

```python
# api/workflows/my_workflow/lg_state.py

from api.workflows.lg_state import ChatState


class MyWorkflowState(ChatState, total=False):
    """내 워크플로 전용 상태."""

    some_field: str
    another_field: list[str]
```

### 2단계. 같은 패키지 안에서 import합니다

`lg_graph.py`에서 상태를 가져올 때는 같은 워크플로 패키지의 `lg_state.py`에서 import합니다.

```python
# api/workflows/my_workflow/lg_graph.py

from api.workflows.my_workflow.lg_state import MyWorkflowState
```

### 3단계. devtools에서 개발할 때도 같은 패턴을 따릅니다

`devtools/workflows/<workflow_id>/lg_state.py`에 상태를 정의하고, `promote` 스크립트가 운영 경로로 옮깁니다.

```python
# devtools/workflows/my_workflow/lg_state.py

from api.workflows.lg_state import ChatState


class MyWorkflowState(ChatState, total=False):
    some_field: str
```

## 주의사항

### ChatState를 직접 수정하지 마세요

`ChatState`에 필드를 추가하면 **모든 워크플로**에 영향이 갑니다. 특정 워크플로에만 필요한 필드는 반드시 해당 워크플로의 전용 상태에 넣어야 합니다.

`ChatState` 변경이 필요하다면 팀과 먼저 협의합니다.

### 상태 필드는 최소한으로 유지합니다

- 여러 턴에 걸쳐 다시 참조할 값만 상태에 넣습니다.
- 한 노드에서만 쓰고 버리는 값은 로컬 변수로 처리합니다.
- 같은 의미의 필드를 중복으로 두지 않습니다.

### `total=False`를 유지합니다

현재 저장소의 모든 상태 클래스는 `TypedDict`에 `total=False`를 지정합니다. 이렇게 하면 모든 필드가 선택적(optional)이 되어, 초기 상태에서 아직 수집하지 않은 슬롯을 자연스럽게 비워 둘 수 있습니다.

## `ChatState` 참고

현재 `ChatState`에 포함된 공통 필드:

| 필드 | 타입 | 용도 |
|------|------|------|
| `messages` | `Annotated[list, add_messages]` | LangGraph 메시지 히스토리 |
| `user_id` | `str` | 사용자 식별자 |
| `channel_id` | `str` | 채널 식별자 |
| `user_message` | `str` | 현재 턴의 사용자 메시지 |
| `conversation_ended` | `bool` | 대화 종료 플래그 |
| `pending_reply` | `str` | 대기 중인 응답 |
