# 워크플로 추가 가이드

이 문서는 이 저장소에서 새 워크플로를 효율적으로 만드는 표준 절차를 팀원용으로 정리한 안내서입니다.

## 한눈에 보는 원칙

- 이 저장소의 새 워크플로는 바로 `api/workflows/`에 만들지 않고 `devtools/workflows/`에서 먼저 작성합니다.
- 워크플로 이름은 `workflow_id` 하나로 통일하고, 디렉터리명·모듈명·MCP 파일명까지 같은 값으로 맞춥니다.
- **워크플로 패키지는 자립적(self-contained)으로 만듭니다.** 상태(`lg_state.py`), 그래프(`lg_graph.py`), 도구 등 모든 구성 요소가 워크플로 패키지 안에 들어갑니다. 다른 워크플로나 공유 파일을 수정할 필요가 없습니다.
- 워크플로 구현은 작은 노드 여러 개로 나누고, 노드 하나에는 한 가지 책임만 두는 편이 유지보수에 유리합니다.
- 멀티턴 대화가 필요하면 임의 상태 저장 로직을 덕지덕지 붙이기보다 LangGraph의 `interrupt`와 `resume` 흐름으로 설계합니다.
- 운영 반영은 수동 복사가 아니라 `promote` 스크립트로 처리합니다.

## 현재 저장소의 표준 작업 순서

1. `workflow_id`를 정합니다.
2. `new_workflow` 스크립트로 dev 워크플로를 생성합니다.
3. 패키지 안의 `lg_state.py`에 `ChatState`를 상속한 전용 상태를 정의합니다.
4. `lg_graph.py`에 resolve-collect-execute 패턴으로 그래프를 구현합니다.
5. 필요하면 dev MCP 도구를 연결합니다.
6. dev runner에서 대화 흐름과 상태 전이를 검증합니다.
7. 테스트를 추가하고 실행합니다.
8. `promote` 스크립트로 운영 경로에 반영합니다.

이 순서를 지키면 실험 코드와 운영 코드를 분리하면서도 등록 실수를 줄일 수 있습니다.

## 1. `workflow_id`를 먼저 설계하는 이유

현재 설정에서는 `workflow_id`가 아래 항목의 기준점 역할을 합니다.

- 워크플로 디렉터리 경로가 됩니다.
- 레지스트리에 등록되는 식별자가 됩니다.
- `handoff_keywords`가 매칭되면 `start_chat`이 넘기는 대상 이름이 됩니다.
- dev MCP 파일명과 운영 MCP 파일명 기준이 됩니다.

따라서 이름은 처음부터 소문자 `snake_case`로 정하고, 의미가 분명한 업무 단위로 짓는 편이 좋습니다.

좋은 예시는 `translator`, `travel_planner`, `invoice_summary` 같은 이름입니다.

피해야 할 예시는 `test`, `newflow`, `temp_work`, `myWorkflow` 같은 이름입니다.

## 2. devtools에서 스캐폴딩하는 방법

새 워크플로는 아래 명령으로 시작합니다.

```bash
python -m devtools.scripts.new_workflow sample_flow
```

이 명령은 현재 템플릿 기준으로 아래 파일을 생성합니다.

```text
devtools/workflows/sample_flow/
├── __init__.py
├── lg_graph.py
└── lg_state.py

devtools/mcp/sample_flow.py
```

이 방식의 장점은 시작 파일 구성이 팀 공통 규칙에 맞춰 고정된다는 점입니다.

## 3. 생성 직후 확인해야 하는 파일

### `devtools/workflows/<workflow_id>/__init__.py`

이 파일은 레지스트리가 읽는 진입점입니다.

현재 템플릿은 아래와 비슷한 형태입니다.

```python
def build_lg_graph():
    from .lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "sample_flow",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": (),
    }
```

이 파일에서 중요한 점은 `get_workflow_definition()`을 반드시 제공해야 한다는 점입니다.

### `devtools/workflows/<workflow_id>/lg_state.py`

이 파일은 이 워크플로 전용 LangGraph 상태를 정의하는 곳입니다.

공유 기본 상태 `ChatState`를 상속하되, 이 워크플로에만 필요한 슬롯만 추가합니다. `ChatState`는 `api/workflows/lg_state.py`에 정의되어 있고, 모든 워크플로가 공통으로 사용하는 `messages`, `user_id`, `channel_id` 등을 포함합니다.

```python
from api.workflows.lg_state import ChatState


class SampleFlowState(ChatState, total=False):
    """sample_flow 워크플로 전용 상태."""

    some_field: str
    another_field: list[str]
```

주의: 공유 `ChatState`에 직접 필드를 추가하지 마세요. 특정 워크플로에만 필요한 필드는 반드시 해당 워크플로의 `lg_state.py`에 정의해야 합니다.

상태 설계에 대한 상세한 가이드는 [워크플로 상태 관리 가이드](workflow_상태_관리_가이드.md)를 참고하세요.

### `devtools/workflows/<workflow_id>/lg_graph.py`

이 파일은 실제 노드와 그래프 구조를 정의하는 곳입니다.

처음부터 복잡하게 만들기보다 진입 노드, 슬롯 수집 노드, 완료 노드 정도로 최소 구조를 먼저 세우는 편이 빠릅니다.

### `devtools/mcp/<workflow_id>.py`

이 파일은 dev 환경에서 쓸 MCP 서버와 도구 등록을 담당합니다.

운영 반영 시 같은 이름으로 `api/mcp/` 아래로 이동하므로 파일명과 역할을 일치시켜 두는 편이 좋습니다.

## 4. 효과적으로 설계하는 방법

### 상태는 작게 시작합니다

- 상태 필드는 실제로 여러 턴에서 다시 참조할 값만 둡니다.
- 사용자 메시지에서 즉시 계산 가능한 값은 굳이 상태에 오래 보관하지 않는 편이 좋습니다.
- 같은 의미의 필드를 중복해서 두지 않는 편이 좋습니다.

예를 들어 번역 워크플로라면 `source_text`, `target_language`, `last_asked_slot` 정도면 충분한 경우가 많습니다.

### 노드는 책임을 분리합니다

- 입력 해석 노드는 입력만 해석합니다.
- 외부 도구 호출 노드는 도구 호출만 담당합니다.
- 최종 응답 생성 노드는 답변 메시지 조립만 담당합니다.

이렇게 나누면 디버깅과 테스트가 쉬워집니다.

### 분기 기준은 코드로 설명 가능해야 합니다

조건 분기가 많아질수록 한 노드에서 모든 것을 처리하지 말고, 분기 판단 함수와 실제 실행 노드를 분리하는 편이 좋습니다.

### 멀티턴은 `interrupt/resume`으로 설계합니다

현재 저장소는 LangGraph 기반 멀티턴 흐름을 전제로 하고 있으므로, 누락 슬롯 확인과 후속 질문은 `interrupt` 기반으로 설계하는 편이 가장 자연스럽습니다.

직접 세션 파일을 덧붙이는 방식보다 그래프 상태와 재개 흐름을 그대로 활용하는 편이 버그를 줄이기 좋습니다.

## 5. LangGraph 그래프 구성 패턴

이 절은 현재 저장소에서 실제로 사용하는 LangGraph 패턴을 정리한 것입니다. 추상적인 LangGraph 문서보다 이 저장소 코드에 맞춘 실전 가이드로 읽어 주세요.

### 그래프의 기본 구조

모든 워크플로 그래프는 `build_lg_graph()` 함수에서 `StateGraph`를 생성하고 반환합니다. 이 함수가 반환하는 것은 아직 compile되지 않은 `StateGraph` 빌더입니다. compile은 상위 오케스트레이터가 담당합니다.

```python
from langgraph.graph import END, StateGraph

from api.workflows.my_workflow.lg_state import MyWorkflowState


def build_lg_graph() -> StateGraph:
    builder = StateGraph(MyWorkflowState)

    # 1. 노드 등록
    builder.add_node("resolve", resolve_node)
    builder.add_node("collect_info", collect_info_node)
    builder.add_node("execute", execute_node)

    # 2. 진입점 설정
    builder.set_entry_point("resolve")

    # 3. 엣지 연결
    builder.add_conditional_edges("resolve", _route_after_resolve)
    builder.add_edge("collect_info", "resolve")
    builder.add_edge("execute", END)

    return builder
```

핵심은 세 단계입니다: 노드 등록 → 진입점 설정 → 엣지 연결.

### 노드 함수의 형태

모든 노드 함수는 상태를 받아서 상태 업데이트 dict를 반환합니다.

```python
def resolve_node(state: MyWorkflowState) -> dict:
    """상태에서 필요한 값을 읽고, 갱신할 값만 반환한다."""

    user_message = state.get("user_message", "")
    # ... 로직 처리 ...
    return {
        "some_field": parsed_value,
        "last_asked_slot": "",
    }
```

주의: 상태 전체를 반환하지 않습니다. 변경할 필드만 반환하면 LangGraph가 기존 상태에 머지합니다.

### 조건부 분기 (conditional edges)

조건부 분기는 이 저장소에서 가장 많이 쓰이는 패턴입니다. `add_conditional_edges`를 사용합니다.

#### 라우팅 함수 작성법

라우팅 함수는 현재 상태를 보고 **다음에 실행할 노드의 이름(문자열)**을 반환합니다.

```python
def _route_after_resolve(state: MyWorkflowState) -> str:
    """resolve 후 다음 노드를 결정한다."""

    # 1. 종료 조건을 가장 먼저 확인
    if state.get("conversation_ended"):
        return END

    # 2. 명시적 슬롯 요청이 있으면 해당 수집 노드로
    if state.get("last_asked_slot") == "target_language":
        return "collect_target_language"

    # 3. 누락 필드 확인 → 해당 수집 노드로
    if not state.get("source_text"):
        return "collect_source_text"
    if not state.get("target_language"):
        return "collect_target_language"

    # 4. 모든 필드가 채워지면 실행 노드로
    return "execute"
```

#### 그래프에 연결하는 방법

```python
builder.add_conditional_edges("resolve", _route_after_resolve)
```

이 한 줄이면 `resolve` 노드 실행 후 `_route_after_resolve` 함수가 호출되어 다음 노드가 결정됩니다.

#### 실제 예시: 번역 워크플로의 조건부 분기

`translator` 워크플로는 아래와 같은 조건부 분기를 사용합니다.

```text
resolve_node
    ├─ conversation_ended=True  → END
    ├─ last_asked_slot="source_text"  → collect_source_text
    ├─ last_asked_slot="target_language"  → collect_target_language
    ├─ source_text 비어 있음  → collect_source_text
    ├─ target_language 비어 있음  → collect_target_language
    └─ 모두 채워짐  → translate
```

#### 실제 예시: 여행 워크플로의 복합 조건부 분기

`travel_planner`는 더 복잡한 조건 분기를 보여줍니다. 여행지가 없을 때 스타일도 없으면 스타일 수집부터, 스타일이 있으면 여행지 추천으로 분기합니다.

```text
resolve_node
    ├─ conversation_ended=True  → END
    ├─ last_asked_slot="travel_style"  → collect_preference
    ├─ last_asked_slot="duration_text"  → collect_trip_context
    ├─ destination 비어 있음
    │   ├─ travel_style도 비어 있음  → collect_preference
    │   └─ travel_style 있음  → recommend_destination
    ├─ duration_text 비어 있음  → collect_trip_context
    └─ 모두 채워짐  → build_plan
```

#### 라우팅 함수 작성 원칙

1. **종료 조건을 맨 위에 둡니다.** `conversation_ended` 같은 플래그를 가장 먼저 확인합니다.
2. **명시적 슬롯 요청을 먼저 확인합니다.** `last_asked_slot`으로 LLM이 지정한 다음 질문을 존중합니다.
3. **누락 필드를 순서대로 확인합니다.** 업무 흐름에서 자연스러운 순서로 확인합니다.
4. **마지막은 기본 실행 경로입니다.** 모든 필드가 채워졌을 때의 경로입니다.
5. **라우팅 함수에 부수효과를 넣지 않습니다.** 상태를 읽기만 하고, 수정은 노드가 담당합니다.

### 고정 엣지 (add_edge)

조건이 필요 없는 경우는 `add_edge`로 직접 연결합니다.

```python
# 수집 후에는 항상 resolve로 돌아간다
builder.add_edge("collect_source_text", "resolve")

# 실행 후에는 항상 종료한다
builder.add_edge("translate", END)
```

이 저장소의 공통 패턴은 **수집 노드 → resolve 노드로 루프백**입니다. 수집 노드는 사용자 입력을 받아 상태에 넣고, resolve 노드가 다시 전체 상태를 평가해서 다음 단계를 결정합니다.

### interrupt / resume 패턴

멀티턴 대화에서 사용자 입력을 기다릴 때는 `interrupt`를 사용합니다.

```python
from langgraph.types import interrupt


def collect_info_node(state: MyWorkflowState) -> dict:
    """사용자에게 정보를 요청하고 응답을 수집한다."""

    user_input = interrupt({"reply": "어떤 정보가 필요한가요?"})
    return {"user_message": user_input, "last_asked_slot": "info_field"}
```

`interrupt`가 호출되면 그래프 실행이 중단되고 `{"reply": "..."}` 값이 호출자에게 반환됩니다. 사용자가 응답하면 오케스트레이터가 `Command(resume=사용자_응답)`으로 그래프를 재개합니다. 재개 시 `interrupt()` 호출이 사용자 응답 값을 반환하고, 노드 함수의 나머지 코드가 실행됩니다.

#### interrupt 사용 원칙

- `interrupt`는 수집 노드에서만 호출합니다. resolve 노드나 실행 노드에서는 호출하지 않습니다.
- `interrupt`에 전달하는 dict에는 항상 `reply` 키를 포함합니다. 오케스트레이터가 이 값을 사용자에게 보여줍니다.
- `interrupt` 후 반환값에는 `user_message`와 `last_asked_slot`을 포함합니다. 이렇게 해야 resolve 노드가 어떤 슬롯에 대한 응답인지 알 수 있습니다.

### resolve-collect-execute 패턴

이 저장소의 모든 워크플로는 아래 구조를 공유합니다.

```text
                ┌──────────────────────────┐
                │       resolve 노드        │
                │  (상태 평가 + 조건 분기)    │
                └────┬────┬────┬────┬──────┘
                     │    │    │    │
            ┌────────┘    │    │    └────────┐
            ▼             ▼    ▼             ▼
      collect_A     collect_B  ...       execute
      (interrupt)   (interrupt)          (실행 후 END)
            │             │
            └──────┬──────┘
                   ▼
              resolve로 루프백
```

1. **resolve 노드**: 현재 상태를 평가하고, 조건부 분기로 다음 노드를 결정합니다.
2. **collect 노드**: 사용자에게 정보를 요청(`interrupt`)하고, 응답을 상태에 넣은 뒤 resolve로 돌아갑니다.
3. **execute 노드**: 모든 정보가 모이면 실제 업무를 수행하고 `END`로 나갑니다.

이 패턴의 장점은 resolve 노드가 "현재 무엇이 빠져 있는지"를 매번 전체 평가하므로, 사용자가 한 번에 여러 정보를 주거나 순서를 건너뛰어도 자연스럽게 대응할 수 있다는 점입니다.

### 서브그래프 연결

`start_chat` 워크플로는 자식 워크플로를 서브그래프로 포함합니다. 이 패턴은 팀원이 직접 구현할 일은 거의 없지만, 구조를 이해하면 디버깅에 도움이 됩니다.

```python
# start_chat의 build_lg_graph() 내부
handoff_subgraphs = _get_handoff_subgraph_builders()

for workflow_id, subgraph_builder in handoff_subgraphs.items():
    builder.add_node(workflow_id, subgraph_builder().compile())

builder.add_conditional_edges("classify", _route_after_classify)

for workflow_id in handoff_subgraphs:
    builder.add_edge(workflow_id, END)
```

핵심은 `add_node`에 compile된 서브그래프를 직접 넣는 방식입니다. 각 워크플로의 `build_lg_graph()`가 `StateGraph`를 반환하면, `start_chat`이 `.compile()`한 뒤 노드로 등록합니다.

### 새 워크플로를 만들 때 최소 그래프 템플릿

아래는 가장 단순한 형태의 워크플로 그래프입니다. 여기서 시작해서 필요에 따라 수집 노드를 추가하면 됩니다.

```python
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.my_workflow.lg_state import MyWorkflowState


def resolve_node(state: MyWorkflowState) -> dict:
    user_message = state.get("user_message", "")
    # LLM 또는 규칙으로 상태를 분석
    if not state.get("required_field"):
        return {"last_asked_slot": "required_field", "pending_reply": "필요한 정보를 알려주세요."}
    return {"last_asked_slot": ""}


def collect_node(state: MyWorkflowState) -> dict:
    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "required_field"}


def execute_node(state: MyWorkflowState) -> dict:
    # 실제 업무 수행
    reply = f"처리 완료: {state.get('required_field', '')}"
    return {"messages": [AIMessage(content=reply)]}


def _route_after_resolve(state: MyWorkflowState) -> str:
    if state.get("conversation_ended"):
        return END
    if state.get("last_asked_slot"):
        return "collect"
    return "execute"


def build_lg_graph() -> StateGraph:
    builder = StateGraph(MyWorkflowState)

    builder.add_node("resolve", resolve_node)
    builder.add_node("collect", collect_node)
    builder.add_node("execute", execute_node)

    builder.set_entry_point("resolve")
    builder.add_conditional_edges("resolve", _route_after_resolve)
    builder.add_edge("collect", "resolve")
    builder.add_edge("execute", END)

    return builder
```

수집할 슬롯이 늘어나면 `collect_a`, `collect_b` 노드를 추가하고 `_route_after_resolve`에서 `last_asked_slot` 값으로 분기하면 됩니다.

## 6. 구현할 때 지켜야 하는 현재 규칙

### 패키지 내부 import

워크플로 패키지 내부의 모듈 간 import는 상대 import를 사용하는 편이 좋습니다.

```python
from .lg_state import SampleFlowState
from .nodes import collect_slot_node
```

단, `lg_graph.py`에서 상태 import는 절대 경로를 사용합니다. 이 패턴이 현재 운영 코드의 표준입니다.

```python
# lg_graph.py에서 같은 패키지의 상태를 가져올 때
from api.workflows.sample_flow.lg_state import SampleFlowState
```

`promote` 스크립트는 `devtools.mcp.` → `api.mcp.` 경로만 치환하므로, 나머지 import는 처음부터 운영 경로 기준으로 작성해야 합니다.

### MCP import

dev 단계에서는 템플릿처럼 `devtools.mcp.<workflow_id>`를 사용합니다.

`promote` 스크립트가 운영 반영 시 이 경로를 `api.mcp.<workflow_id>`로 자동 치환합니다.

### 도구 등록 호출 위치

도구가 필요한 워크플로라면 `build_lg_graph()` 경로에서 등록 함수를 한 번 호출하도록 두는 편이 현재 구조와 가장 잘 맞습니다.

실제 `translator` 워크플로도 `build_lg_graph()` 진입 시 번역 도구 등록을 수행합니다.

## 7. `handoff_keywords`를 정하는 방법

`handoff_keywords`는 `start_chat`에서 사용자 발화를 보고 어떤 서브워크플로로 넘길지 결정하는 기준입니다.

현재 구현은 사용자 메시지를 소문자로 바꾼 뒤, 키워드가 포함되어 있는지만 확인합니다.

따라서 키워드는 아래 원칙으로 정하는 편이 좋습니다.

- 너무 넓은 일반 단어는 피합니다.
- 업무 의미가 분명한 표현을 넣습니다.
- 한국어와 영어를 함께 쓰는 업무라면 두 언어를 같이 넣습니다.
- 이미 다른 워크플로가 쓰는 키워드와 겹치지 않게 조심합니다.

예를 들어 `번역`, `translate`, `translation` 정도는 괜찮지만 `문서`, `도움`, `계획` 같은 넓은 단어는 오분류를 일으키기 쉽습니다.

### 좋은 키워드 세트를 만드는 절차

현재 설정에서는 아래 순서로 키워드를 정하는 편이 가장 실무적입니다.

1. 사용자가 실제로 말할 요청 문장을 먼저 5개에서 10개 정도 적습니다.
2. 그 문장에서 반복되는 업무 표현만 추려 후보 키워드를 만듭니다.
3. 한글 표현과 영어 표현이 모두 필요한지 판단합니다.
4. 다른 워크플로와 겹치는 일반 단어를 제거합니다.
5. `start_chat`으로 직접 넣어 보고 오분류가 없는지 확인합니다.

즉, 키워드는 먼저 정답 단어를 상상해서 넣는 방식보다, 실제 요청 문장에서 역으로 뽑아내는 방식이 더 안정적입니다.

### 좋은 키워드의 형태

- 가능하면 동작과 목적이 함께 드러나는 구문을 씁니다.
- 한 단어보다 두세 단어짜리 표현을 우선 검토합니다.
- 업무가 명확하면 명사 하나도 가능하지만, 범용 명사는 피하는 편이 좋습니다.
- 같은 의미의 별칭은 넣되, 거의 같은 오탈자 변형을 과도하게 늘리지는 않는 편이 좋습니다.

예를 들어 여행 워크플로라면 `여행 계획`, `여행 일정`, `travel planner`는 괜찮지만 `여행`, `계획`만 단독으로 두는 방식은 넓게 잡힐 가능성이 큽니다.

### 현재 구조에서 특히 조심해야 하는 점

현재 `start_chat` 라우팅은 `첫 번째로 매칭된 워크플로`를 선택합니다.

워크플로 발견 순서는 패키지 스캔 순서에 영향을 받으므로, 키워드가 서로 겹치면 의도하지 않은 워크플로가 먼저 선택될 수 있습니다.

따라서 아래 패턴은 피하는 편이 좋습니다.

- 여러 워크플로가 `계획`, `추천`, `분석` 같은 단어를 공통으로 쓰는 방식입니다.
- 상위 개념 키워드와 하위 개념 키워드를 같이 두는 방식입니다.
- 다른 워크플로의 대표 키워드를 일부만 공유하는 방식입니다.

### 추천 검증 방법

키워드를 정한 뒤에는 아래처럼 양성과 음성 예시를 같이 검증하는 편이 좋습니다.

- 양성 예시는 이 워크플로로 반드시 들어가야 하는 문장입니다.
- 음성 예시는 비슷해 보이지만 다른 워크플로로 가야 하거나 일반 대화로 남아야 하는 문장입니다.

예를 들어 번역 워크플로를 검증한다면 아래처럼 확인할 수 있습니다.

- 양성 예시는 `이 문장을 영어로 번역해 줘`, `translate this into Japanese` 같은 문장입니다.
- 음성 예시는 `영어 공부 방법 알려줘`, `일본 여행 계획 짜줘` 같은 문장입니다.

이 검증은 `devtools.workflow_runner`에서 `start_chat`으로 직접 넣어 보는 방식으로 확인하는 편이 좋습니다.

## 8. dev runner로 검증하는 방법

로컬 검증은 아래 명령으로 시작합니다.

```bash
python -m devtools.workflow_runner.app
```

이 runner는 `devtools/workflows/`를 자동 탐색해서 워크플로 목록을 구성합니다.

검증할 때는 아래 항목을 반드시 확인하는 편이 좋습니다.

- 첫 메시지에서 기대한 노드로 진입하는지 확인합니다.
- 누락 슬롯이 있을 때 질문이 자연스럽게 반환되는지 확인합니다.
- 다음 메시지에서 `resume`이 정상 동작하는지 확인합니다.
- 상태 패널에서 필드 값이 기대대로 쌓이는지 확인합니다.
- 완료 후 불필요한 상태가 남지 않는지 확인합니다.

## 9. 테스트를 붙이는 방법

문서만으로는 품질을 보장하기 어렵기 때문에 최소 테스트는 함께 추가하는 편이 좋습니다.

권장하는 최소 테스트 범위는 아래와 같습니다.

- 정상 완료 경로 테스트를 작성합니다.
- 필수 슬롯이 비어 있을 때 interrupt가 발생하는지 테스트합니다.
- 후속 입력으로 resume이 이어지는지 테스트합니다.
- 레지스트리에서 `workflow_id`를 정상 발견하는지 테스트합니다.

기본 실행 명령은 아래와 같습니다.

```bash
pytest tests/ -v
```

## 10. 운영 반영 방법

검증이 끝나면 아래 명령으로 운영 경로에 반영합니다.

```bash
python -m devtools.scripts.promote sample_flow
```

이 스크립트는 현재 설정 기준으로 아래 작업을 수행합니다.

1. `devtools/workflows/sample_flow/`를 `api/workflows/sample_flow/`로 복사합니다.
2. `devtools/mcp/sample_flow.py`를 `api/mcp/sample_flow.py`로 복사합니다.
3. `devtools.mcp.` import를 `api.mcp.` import로 자동 치환합니다.
4. import 검증을 수행합니다.
5. 검증이 통과하면 dev 원본을 삭제합니다.

즉, 운영 반영은 수동 복사보다 `promote` 스크립트로 처리하는 편이 안전합니다.

## 11. 팀에서 자주 실수하는 지점

- `workflow_id`와 디렉터리명을 다르게 만드는 실수를 합니다.
- `get_workflow_definition()`에서 `build_lg_graph`를 빠뜨리는 실수를 합니다.
- `handoff_keywords`를 너무 넓게 잡아 엉뚱한 요청이 라우팅되는 실수를 합니다.
- dev 단계에서 절대 import를 남겨 promotion 후 import 오류를 만드는 실수를 합니다.
- 도구 등록 함수는 만들었지만 실제 그래프 빌드 경로에서 호출하지 않아 런타임에 도구가 비어 있는 실수를 합니다.
- 워크플로 전용 상태를 공유 `api/workflows/lg_state.py`에 직접 추가하는 실수를 합니다. 전용 상태는 반드시 자기 패키지 안의 `lg_state.py`에 정의해야 합니다.

## 12. 권장 체크리스트

- 새 워크플로는 `new_workflow`로 시작합니다.
- 워크플로 전용 상태는 자기 패키지 안의 `lg_state.py`에 `ChatState`를 상속해서 정의합니다.
- 상태 필드는 꼭 필요한 값만 둡니다.
- 노드는 한 가지 책임만 갖게 나눕니다.
- `handoff_keywords`는 좁고 구체적으로 정합니다.
- dev runner에서 멀티턴 흐름을 직접 확인합니다.
- 자동 테스트를 추가합니다.
- 운영 반영은 `promote`로 수행합니다.
- 공유 파일(`api/workflows/lg_state.py`, `registry.py` 등)은 수정하지 않습니다.

이 체크리스트를 지키면 새 워크플로를 빠르게 만들면서도 현재 저장소 규칙과 충돌하지 않게 유지할 수 있습니다.
