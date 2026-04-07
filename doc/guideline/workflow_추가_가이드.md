# Workflow 추가 가이드

시각적으로 정리한 보조 자료가 필요하면 같은 폴더의 `workflow_추가_가이드.html`도 함께 본다.

## 목적

이 문서는 동료가 이 저장소에 새 업무 workflow를 추가할 때 따라야 할 기준을 정리한 문서다.
목표는 아래 두 가지다.

- 현재 구성된 `Cube -> queue -> worker -> LangGraph orchestrator -> workflow` 흐름에 자연스럽게 붙을 것
- 누가 추가해도 구조, 상태 저장, handoff, 테스트 방식이 흔들리지 않을 것

## 한눈에 보는 실행 흐름

```text
Cube 메시지 수신
-> api/cube/router.py
-> Redis queue 적재
-> worker 처리
-> api/workflows/lg_orchestrator.handle_message()
-> start_chat 루트 그래프 → classify → 서브그래프 handoff 또는 일반 대화
-> LangGraph checkpointer가 상태 자동 저장 (MongoDB 또는 MemorySaver)
-> Cube 응답 전송
```

중요한 점은 다음과 같다.

- 새 workflow는 `api/workflows/<workflow_id>/` 패키지로 추가한다.
- workflow 등록은 수동이 아니라 `api/workflows/registry.py`가 자동 탐색한다.
- 본선 실행은 LangGraph `StateGraph` 기반이다. `interrupt()`로 사용자 입력을 요청하고, `Command(resume=...)`로 재개한다.
- 상태 저장은 LangGraph checkpointer가 자동 처리한다 (MongoDB 또는 MemorySaver).

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
- 외부 API, DB, 파일 저장소 의존성을 테스트에서 mock 할 수 있는가
- 실패 시 사용자에게 어떤 안내 문구를 줄지 정했는가

## 권장 폴더 구조

최소 권장 구조는 아래와 같다.

```text
api/workflows/<workflow_id>/
  __init__.py
  lg_graph.py
  state.py          # 선택 (레거시 어댑터용)
  nodes.py          # 선택 (레거시 어댑터용)
  lg_adapter.py     # 선택 (devtools 시각화 호환)
  prompts.py        # 선택
  tools.py          # 선택 (MCP 도구 등록)
  rag/              # 선택
```

현재 코드베이스 기준 역할은 다음과 같다.

- `__init__.py`: workflow 정의 export (`get_workflow_definition()` + `build_lg_graph()`)
- `lg_graph.py`: LangGraph `StateGraph` 정의 — 노드, 엣지, 조건 분기, `interrupt()` 포함
- `state.py`: 레거시 어댑터용 `WorkflowState` 기반 상태 정의
- `nodes.py`: 레거시 어댑터용 `NodeResult` 기반 노드 함수
- `lg_adapter.py`: LangGraph 그래프를 기존 `build_graph()` dict 인터페이스로 래핑 (devtools 호환)
- `prompts.py`: 프롬프트 상수
- `tools.py`: MCP 도구 서버/핸들러 등록
- `rag/`: workflow 전용 검색 capability

## LangGraph 상태 정의

모든 workflow 상태는 `api/workflows/lg_state.py`의 `ChatState`를 확장한 `TypedDict`로 정의한다.

`ChatState` 공통 필드:

```python
class ChatState(TypedDict, total=False):
    messages: Annotated[list, add_messages]  # LangGraph 메시지 리듀서
    user_id: str
    channel_id: str
    user_message: str
    workflow_id: str
```

workflow 전용 상태 예시:

```python
class MyFlowState(ChatState, total=False):
    request_type: str
    confirmed: bool
    result_payload: dict[str, str]
```

규칙:

- 모든 필드에 기본값이 필요하므로 `total=False`를 사용한다.
- `messages`는 LangGraph `add_messages` 리듀서로 자동 누적된다.
- 상태는 LangGraph checkpointer가 자동 직렬화하므로 단순 자료형을 사용한다.

## 필수 계약

### 1. `__init__.py`

workflow 패키지는 두 가지를 export해야 한다.

**`build_lg_graph()` (필수)**: LangGraph 서브그래프 빌더. `start_chat`이 서브그래프로 주입할 때 사용한다.

**`get_workflow_definition()` (필수)**: workflow 메타데이터. registry가 자동 탐색에 사용한다.

예시:

```python
def build_lg_graph():
    from api.workflows.my_flow.lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "build_graph": build_graph,          # 레거시 어댑터 (devtools 호환)
        "build_lg_graph": build_lg_graph,    # LangGraph 서브그래프 빌더
        "state_cls": MyFlowWorkflowState,    # 레거시 상태 클래스
        "handoff_keywords": ("my flow", "내 업무"),
        "tool_tags": (),                     # MCP 도구 태그 (선택)
    }
```

규칙:

- `workflow_id`는 전역에서 유일해야 한다.
- `handoff_keywords`는 `start_chat`에서 해당 workflow로 넘기고 싶을 때만 넣는다.
- `handoff_keywords`는 등록 시 소문자/trim 정규화된다. 비교는 substring 방식이므로 과도하게 일반적인 단어는 피한다.

### 2. `lg_graph.py`

LangGraph `StateGraph`를 구성하는 핵심 파일이다. 노드 함수와 그래프 빌더를 모두 이 파일에 둔다.

예시:

```python
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.lg_state import MyFlowState


def entry_node(state: MyFlowState) -> dict:
    """초기 요청을 파싱한다."""
    user_message = state.get("user_message", "")
    if not user_message.strip():
        return {"request_type": ""}
    return {"request_type": "default"}


def collect_request_node(state: MyFlowState) -> dict:
    """사용자에게 요청 내용을 물어본다."""
    user_input = interrupt({"reply": "처리할 요청을 알려주세요."})
    return {"user_message": user_input}


def process_request_node(state: MyFlowState) -> dict:
    """요청을 처리하고 응답을 반환한다."""
    request = state.get("user_message", "")
    return {
        "messages": [AIMessage(content=f"요청을 접수했습니다: {request}")],
        "confirmed": True,
    }


def _route_after_entry(state: MyFlowState) -> str:
    if not state.get("request_type"):
        return "collect_request"
    return "process_request"


def build_lg_graph() -> StateGraph:
    builder = StateGraph(MyFlowState)

    builder.add_node("entry", entry_node)
    builder.add_node("collect_request", collect_request_node)
    builder.add_node("process_request", process_request_node)

    builder.set_entry_point("entry")
    builder.add_conditional_edges("entry", _route_after_entry)
    builder.add_edge("collect_request", "entry")
    builder.add_edge("process_request", END)

    return builder
```

핵심 패턴:

| 이전 (커스텀) | 현재 (LangGraph) |
|---------------|------------------|
| `NodeResult(action="wait", reply="...")` | `interrupt({"reply": "..."})` |
| `NodeResult(action="resume", next_node_id="X")` | 조건부 엣지로 라우팅 |
| `NodeResult(action="complete", reply="...")` | `AIMessage` 반환 + `END` 엣지 |
| `state.source_text` (dataclass) | `state.get("source_text", "")` (TypedDict) |
| `NodeResult.data_updates` | dict 반환값이 곧 상태 업데이트 |

실무 규칙:

- 노드 함수는 `(state: MyFlowState) -> dict` 시그니처를 따른다.
- 응답은 `AIMessage`를 `messages` 키에 넣어 반환한다.
- 사용자 입력이 필요하면 `interrupt({"reply": "안내 문구"})`를 호출한다.
- 라우팅 함수는 부작용 없이 상태만 읽는다.
- 외부 API 호출 전후, 파싱 결과, 핵심 분기 정도는 로그를 남긴다.

## handoff 규칙

이 저장소의 기본 진입점은 `start_chat` 루트 그래프다.
특정 업무 workflow로 진입시키고 싶다면 `start_chat`이 메시지를 분류해 서브그래프로 handoff 한다.

규칙:

- `start_chat`은 일반 대화와 업무 workflow handoff를 담당한다.
- handoff 대상 workflow만 `handoff_keywords`를 가진다.
- 키워드는 `start_chat/lg_graph.py`에서 `_get_handoff_subgraph_builders()`로 동적 탐색되어 서브그래프 노드로 추가된다.
- 서브그래프가 `END`에 도달하면 `start_chat` 루트 그래프도 `END`로 종료된다.
- 다음 사용자 턴은 새 진입점처럼 다시 처리된다.

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
- LangGraph 상태 정의는 `api/workflows/lg_state.py`에 추가한다.
- 외부 연동 코드는 노드 내부에 직접 퍼뜨리지 말고 필요하면 workflow 하위 `tools.py`, `rag/`, 또는 별도 서비스 모듈로 분리한다.
- 여러 workflow에서 공통으로 쓰는 로직이 생기면 각 workflow에 복붙하지 말고 공용 계층으로 승격한다.
- 테스트 없이 workflow만 추가하지 않는다.

## 가급적 건드리지 말아야 할 파일

아래 파일은 workflow를 "추가"하는 작업만 할 때는 수정하지 않는 것을 원칙으로 한다.

- `api/__init__.py`
- `api/blueprint_loader.py`
- `api/workflows/registry.py`
- `api/workflows/lg_orchestrator.py`
- `api/workflows/langgraph_checkpoint.py`
- 기존 workflow 패키지 전체
- `api/workflows/start_chat/`

예외는 아래처럼 명확한 경우만 허용한다.

- 공통 버그를 수정해야 해서 모든 workflow에 영향을 주는 문제를 해결할 때
- `start_chat`의 분류 정책 자체를 변경해야 할 때
- 공용 상태 저장 규약을 바꿔야 할 정도의 구조 변경을 팀이 합의했을 때
- 기존 workflow를 실제로 개선하거나 유지보수하는 명시적 작업을 맡았을 때

예외 작업을 할 때는 아래를 같이 남기는 것을 권장한다.

- 왜 새 workflow 패키지 추가만으로 해결되지 않는지
- 영향받는 workflow 범위
- 회귀 테스트 항목

## 테스트 규칙

새 workflow를 추가하면 최소한 아래를 검증한다.

- 등록 테스트: registry가 workflow를 발견하는지
- 기본 흐름 테스트: entry부터 완료까지 기대한 노드 흐름을 타는지
- interrupt 테스트: `interrupt()` 후 `Command(resume=...)` 로 이어지는지
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
2. `api/workflows/lg_state.py`에 workflow 전용 `TypedDict` 상태를 추가한다.
3. `api/workflows/<workflow_id>/` 패키지를 만든다.
4. `lg_graph.py`에서 노드 함수와 `StateGraph`를 정의한다.
5. `__init__.py`에서 `build_lg_graph()`와 `get_workflow_definition()`을 export 한다.
6. `handoff_keywords`가 필요하면 추가한다.
7. 테스트를 붙여 기본 흐름과 interrupt/resume을 고정한다.
8. 그 다음 외부 API, RAG, MCP 도구 같은 실제 capability를 연결한다.
9. (선택) devtools 호환이 필요하면 `lg_adapter.py`, `nodes.py`, `state.py`를 추가한다.

## 최소 스캐폴드 예시

```text
api/workflows/my_flow/
  __init__.py
  lg_graph.py
```

`api/workflows/lg_state.py`에 추가:

```python
class MyFlowState(ChatState, total=False):
    request_text: str
```

`__init__.py`:

```python
def build_lg_graph():
    from api.workflows.my_flow.lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "my_flow",
        "entry_node_id": "entry",
        "build_graph": None,
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": ("my flow", "내 업무"),
    }
```

`lg_graph.py`:

```python
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.lg_state import MyFlowState


def entry_node(state: MyFlowState) -> dict:
    text = state.get("user_message", "").strip()
    if not text:
        return {"request_text": ""}
    return {"request_text": text}


def collect_request_node(state: MyFlowState) -> dict:
    user_input = interrupt({"reply": "처리할 요청을 알려주세요."})
    return {"user_message": user_input, "request_text": user_input}


def process_request_node(state: MyFlowState) -> dict:
    text = state.get("request_text", "")
    return {"messages": [AIMessage(content=f"요청을 접수했습니다: {text}")]}


def _route_after_entry(state: MyFlowState) -> str:
    if not state.get("request_text"):
        return "collect_request"
    return "process_request"


def build_lg_graph() -> StateGraph:
    builder = StateGraph(MyFlowState)

    builder.add_node("entry", entry_node)
    builder.add_node("collect_request", collect_request_node)
    builder.add_node("process_request", process_request_node)

    builder.set_entry_point("entry")
    builder.add_conditional_edges("entry", _route_after_entry)
    builder.add_edge("collect_request", "entry")
    builder.add_edge("process_request", END)

    return builder
```

## 실전 샘플 참고

실제 동작하는 샘플이 필요하면 아래 구현을 그대로 열어보면 된다.

- `api/workflows/translator/lg_graph.py` — interrupt 기반 슬롯 수집 + MCP 도구 호출
- `api/workflows/travel_planner/lg_graph.py` — 조건부 라우팅 + 다단계 정보 수집
- `api/workflows/chart_maker/lg_graph.py` — 순차 interrupt 패턴

이 샘플들은 아래 패턴을 모두 포함한다.

- `interrupt()`로 부족한 정보 재질문
- `Command(resume=...)`로 다음 턴에서 재개
- `AIMessage`로 최종 응답 반환
- 조건부 엣지로 상태 기반 라우팅

## 자주 생기는 실수

- workflow 패키지를 만들고도 `build_lg_graph()`를 export하지 않음
- `workflow_id`를 패키지명과 다르게 정해 놓고 테스트를 안 함
- `interrupt()`를 호출하면서 사용자 안내 문구를 주지 않음
- 노드 함수가 dict 대신 다른 타입을 반환함
- `AIMessage`를 `messages` 키에 넣지 않아 응답이 전달되지 않음
- handoff 키워드를 너무 넓게 잡아 엉뚱한 업무로 분기됨
- LangGraph 상태를 `lg_state.py`에 추가하지 않고 별도 파일에 정의함
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

이 문서를 기준으로 추가하면 동료 workflow도 현재 registry, LangGraph checkpointer, start_chat handoff, 시각화 페이지와 자연스럽게 맞물린다.
