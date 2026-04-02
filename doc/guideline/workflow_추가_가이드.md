# Workflow 추가 가이드

## 목적

이 문서는 동료가 이 저장소에 새 업무 workflow를 추가할 때 따라야 할 기준을 정리한 문서다.
목표는 아래 두 가지다.

- 현재 구성된 `Cube -> queue -> worker -> orchestrator -> workflow` 흐름에 자연스럽게 붙을 것
- 누가 추가해도 구조, 상태 저장, handoff, 테스트 방식이 흔들리지 않을 것

## 한눈에 보는 실행 흐름

```text
Cube 메시지 수신
-> api/cube/router.py
-> Redis queue 적재
-> worker 처리
-> api/workflows/orchestrator.handle_message()
-> 현재 workflow graph 실행
-> NodeResult에 따라 resume / wait / handoff / complete
-> 상태 저장
-> Cube 응답 전송
```

중요한 점은 다음과 같다.

- 새 workflow는 `api/workflows/<workflow_id>/` 패키지로 추가한다.
- workflow 등록은 수동이 아니라 `api/workflows/registry.py`가 자동 탐색한다.
- 런타임에서 실제 진행은 각 node가 반환하는 `NodeResult` 기준으로 결정된다.
- `graph.py`의 `edges`와 `router`는 시각화와 문서화에 유용하지만, 실행 제어의 핵심은 `NodeResult.next_node_id`와 `action`이다.

## 새 workflow를 만들기 전에 준비할 것

- 이 workflow가 해결할 업무 범위를 한 줄로 정의한다.
- `workflow_id`를 미리 정한다.
- 첫 사용자 턴에 바로 처리할지, 부족한 정보를 재질문할지 정한다.
- 어떤 상태값을 턴 간에 유지해야 하는지 정한다.
- 외부 의존성이 있으면 어떤 환경 변수와 mock 전략이 필요한지 정한다.
- `start_chat`에서 handoff 받을 대상인지 결정한다.
- 사용자 응답 문구를 한국어 기준으로 정리한다.

사전 체크리스트:

- `workflow_id`는 다른 패키지와 중복되지 않는가
- handoff 키워드가 너무 넓어서 다른 workflow와 충돌하지 않는가
- 상태에 넣을 값이 JSON 직렬화 가능한가
- 외부 API, DB, 파일 저장소 의존성을 테스트에서 mock 할 수 있는가
- 실패 시 사용자에게 어떤 안내 문구를 줄지 정했는가

## 권장 폴더 구조

최소 권장 구조는 아래와 같다.

```text
api/workflows/<workflow_id>/
  __init__.py
  graph.py
  nodes.py
  state.py
  routing.py          # 선택
  prompts.py          # 선택
  rag/                # 선택
  agent/              # 선택
```

현재 코드베이스 기준 역할은 다음과 같다.

- `__init__.py`: workflow 정의 export
- `graph.py`: 노드 목록, entry node, 시각화용 edge 정의
- `nodes.py`: 실제 업무 로직과 `NodeResult` 반환
- `state.py`: `WorkflowState`를 확장한 전용 상태 정의
- `routing.py`: 분기 판단 함수 모음
- `prompts.py`: 프롬프트 상수
- `rag/`, `agent/`: workflow 전용 capability

## 필수 계약

### 1. `__init__.py`

workflow 패키지는 `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`을 export해야 한다.
현재 저장소에서는 `get_workflow_definition()` 함수 방식을 기본 규약으로 본다.

필수 항목:

- `workflow_id`
- `entry_node_id`
- `build_graph`

권장 항목:

- `state_cls`
- `handoff_keywords`

예시:

```python
from __future__ import annotations


def get_workflow_definition() -> dict[str, object]:
    from api.workflows.my_flow.graph import build_graph
    from api.workflows.my_flow.state import MyFlowState

    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": MyFlowState,
        "handoff_keywords": ("my flow", "내 업무"),
    }
```

규칙:

- `workflow_id`는 전역에서 유일해야 한다.
- `handoff_keywords`는 `start_chat`에서 해당 workflow로 넘기고 싶을 때만 넣는다.
- `handoff_keywords`는 등록 시 소문자/trim 정규화된다. 비교는 substring 방식이므로 과도하게 일반적인 단어는 피한다.

### 2. `state.py`

전용 상태는 반드시 `WorkflowState` 하위 dataclass로 정의한다.

예시:

```python
from dataclasses import dataclass, field

from api.workflows.models import WorkflowState


@dataclass
class MyFlowState(WorkflowState):
    request_type: str = ""
    confirmed: bool = False
    result_payload: dict[str, str] = field(default_factory=dict)
```

규칙:

- workflow 전용 필드는 기본값을 가져야 한다.
- 저장 상태는 JSON 파일로 직렬화되므로 단순 자료형 위주로 유지한다.
- `data_updates`에 넣은 값은 `state.data`와 상태 객체 양쪽에 반영된다.
- 다음 턴에서도 필요할 값은 `NodeResult.data_updates`로 반드시 저장한다.

### 3. `nodes.py`

모든 node 함수는 아래 계약을 따른다.

```python
def some_node(state: MyFlowState, user_message: str) -> NodeResult:
    ...
```

`NodeResult.action` 의미:

- `resume`: 같은 사용자 턴 안에서 다음 node로 즉시 이동
- `wait`: 사용자 추가 입력을 기다리고 멈춤
- `reply`: 응답을 반환하고 현재 턴 종료
- `handoff`: 다른 workflow로 전환
- `complete`: 현재 workflow 완료

실무 규칙:

- `wait`, `reply`, `complete`처럼 턴을 멈추는 액션에는 사용자용 `reply`를 함께 넣는 것을 기본으로 한다.
- `reply` 없이 멈추면 상위 처리에서 `"[workflow_id] 처리 완료."` 같은 fallback 문구가 나갈 수 있다.
- 다음 node로 넘어가야 하면 `next_node_id`를 명시한다.
- 다른 workflow로 넘길 때는 `next_workflow_id`를 명시한다.
- 외부 API 호출 전후, 파싱 결과, 핵심 분기 정도는 로그를 남긴다.

예시:

```python
from api.workflows.models import NodeResult


def entry_node(state: MyFlowState, user_message: str) -> NodeResult:
    if not user_message.strip():
        return NodeResult(
            action="wait",
            reply="요청 내용을 한 줄로 알려주세요.",
            next_node_id="collect_request",
        )

    return NodeResult(
        action="resume",
        next_node_id="process_request",
        data_updates={"request_type": "default"},
    )
```

### 4. `graph.py`

`build_graph()`는 dict를 반환한다.

현재 저장소에서 사실상 필요한 항목:

- `workflow_id`
- `entry_node_id`
- `nodes`

권장 항목:

- `edges`
- `router`

예시:

```python
from api.workflows.my_flow import nodes, routing


def build_graph() -> dict[str, object]:
    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_request": nodes.collect_request_node,
            "process_request": nodes.process_request_node,
        },
        "edges": [
            ("entry", "collect_request", "입력 부족"),
            ("entry", "process_request", "입력 충분"),
            ("collect_request", "process_request"),
        ],
        "router": routing.route_next_node,
    }
```

주의:

- 실제 실행 제어는 `edges`가 아니라 node가 반환한 `NodeResult`로 이뤄진다.
- 그래도 `edges`는 `/workflows/<workflow_id>` 시각화와 코드 가독성에 도움이 되므로 같이 유지하는 것이 좋다.
- node id 문자열은 상태 저장과 이어달리기에 쓰이므로 중간에 자주 바꾸지 않는 편이 안전하다.

## handoff 규칙

이 저장소의 기본 진입점은 `start_chat`이다.
특정 업무 workflow로 진입시키고 싶다면 `start_chat`이 메시지를 분류해 handoff 한다.

규칙:

- `start_chat`은 일반 대화와 업무 workflow handoff를 담당한다.
- handoff 대상 workflow만 `handoff_keywords`를 가진다.
- 키워드는 `api/workflows/start_chat/routing.py`에서 substring으로 판별된다.
- child workflow가 `complete`하거나, `reply` 후 `next_node_id`가 `None` 또는 `"done"`이면 부모로 복귀할 수 있다.
- `start_chat`로 복귀한 뒤에는 다음 사용자 턴을 새 진입점처럼 다시 처리한다.

실무 팁:

- workflow 이름 자체보다 사용자가 실제로 말할 표현을 키워드로 넣는다.
- 영어/한국어 혼용 표현이 있으면 둘 다 넣는다.
- 오탐이 많아질 수 있는 일반 단어는 피한다.

## 코드베이스 규칙

동료가 새 workflow를 추가할 때 아래 규칙을 지키면 현재 구성과 충돌하지 않는다.

- 새 workflow는 반드시 `api/workflows/` 하위 독립 패키지로 만든다.
- 앱 초기화 코드나 registry에 수동 등록 코드를 넣지 않는다.
- 환경 변수는 `api/config.py`에 추가하고 코드에서 하드코딩하지 않는다.
- 파일 경로는 `pathlib.Path`를 사용한다.
- 사용자 노출 문구는 한국어 워크플로에 맞게 유지한다.
- 외부 연동 코드는 node 내부에 직접 퍼뜨리지 말고 필요하면 workflow 하위 `agent/`, `rag/`, 또는 별도 서비스 모듈로 분리한다.
- 여러 workflow에서 공통으로 쓰는 로직이 생기면 각 workflow에 복붙하지 말고 `api/workflows/common/` 또는 infra/service 계층으로 승격한다.
- state에 connection 객체, client 객체, 함수 객체 같은 비직렬화 값을 넣지 않는다.
- 테스트 없이 workflow만 추가하지 않는다.

## 테스트 규칙

새 workflow를 추가하면 최소한 아래를 검증한다.

- 등록 테스트: registry가 workflow를 발견하는지
- 기본 흐름 테스트: entry부터 완료까지 기대한 node 흐름을 타는지
- 재질문 테스트: `wait` 후 다음 턴에서 이어지는지
- handoff 테스트: `start_chat`에서 해당 workflow로 분기되는지
- 외부 의존성 테스트: API, Redis, 파일 시스템 호출을 mock 했는지

권장 파일명:

- `tests/test_<workflow_id>_workflow.py`

권장 실행:

```bash
pytest tests/test_workflow_registry.py tests/test_start_chat_workflow.py tests/test_<workflow_id>_workflow.py -v
```

추가 확인:

- `python index.py`로 앱 기동
- `/workflows`에서 새 workflow가 보이는지 확인
- `/workflows/<workflow_id>`에서 그래프가 시각화되는지 확인

## 구현 순서 추천

1. 업무 범위와 상태 필드를 먼저 정한다.
2. `api/workflows/<workflow_id>/` 패키지와 4개 기본 파일을 만든다.
3. `__init__.py`에서 workflow 정의를 export 한다.
4. `state.py`에 workflow 전용 상태를 추가한다.
5. `nodes.py`에서 `wait`, `resume`, `complete` 기준의 대화 흐름을 먼저 만든다.
6. `graph.py`에 node id와 edge를 정리한다.
7. `handoff_keywords`가 필요하면 추가한다.
8. 테스트를 먼저 붙여 기본 흐름과 재진입을 고정한다.
9. 그 다음 외부 API, RAG, agent 같은 실제 capability를 연결한다.

## 최소 스캐폴드 예시

```text
api/workflows/my_flow/
  __init__.py
  graph.py
  nodes.py
  state.py
```

`__init__.py`

```python
from __future__ import annotations


def get_workflow_definition() -> dict[str, object]:
    from api.workflows.my_flow.graph import build_graph
    from api.workflows.my_flow.state import MyFlowState

    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "build_graph": build_graph,
        "state_cls": MyFlowState,
        "handoff_keywords": ("my flow", "내 업무"),
    }
```

`state.py`

```python
from dataclasses import dataclass

from api.workflows.models import WorkflowState


@dataclass
class MyFlowState(WorkflowState):
    request_text: str = ""
```

`nodes.py`

```python
from api.workflows.models import NodeResult
from api.workflows.my_flow.state import MyFlowState


def entry_node(state: MyFlowState, user_message: str) -> NodeResult:
    text = user_message.strip()
    if not text:
        return NodeResult(
            action="wait",
            reply="처리할 요청을 알려주세요.",
            next_node_id="collect_request",
        )

    return NodeResult(
        action="complete",
        reply=f"요청을 접수했습니다: {text}",
        data_updates={"request_text": text},
    )


def collect_request_node(state: MyFlowState, user_message: str) -> NodeResult:
    text = user_message.strip()
    return NodeResult(
        action="complete",
        reply=f"요청을 접수했습니다: {text}",
        data_updates={"request_text": text},
    )
```

`graph.py`

```python
from api.workflows.my_flow import nodes


def build_graph() -> dict[str, object]:
    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "nodes": {
            "entry": nodes.entry_node,
            "collect_request": nodes.collect_request_node,
        },
        "edges": [
            ("entry", "collect_request", "입력 없음"),
        ],
    }
```

## 자주 생기는 실수

- workflow 패키지를 만들고도 `get_workflow_definition()`을 export하지 않음
- `workflow_id`를 패키지명과 다르게 정해 놓고 테스트를 안 함
- `wait`를 반환하면서 사용자 안내 문구를 주지 않음
- `NodeResult.data_updates` 없이 상태를 로컬 변수로만 들고 감
- handoff 키워드를 너무 넓게 잡아 엉뚱한 업무로 분기됨
- 상태에 비직렬화 객체를 넣어 저장 단계에서 깨짐
- registry에 수동 등록 코드를 추가해 자동 탐색 규약을 깨뜨림
- 외부 API 호출을 테스트에서 직접 때려 flaky test를 만듦

## 팀 권장 운영 방식

- 먼저 skeleton workflow와 테스트를 올리고, 이후 실제 업무 로직을 단계적으로 붙인다.
- 공통 기능이 2개 workflow 이상에서 반복되면 바로 공용 계층으로 옮길지 검토한다.
- PR에는 아래를 꼭 포함한다.

```text
- 무엇을 위한 workflow인지
- handoff 대상인지
- 필요한 환경 변수
- 테스트 결과
- 아직 stub 인 부분
```

이 문서를 기준으로 추가하면 동료 workflow도 현재 registry, state 저장, start_chat handoff, 시각화 페이지와 자연스럽게 맞물린다.
