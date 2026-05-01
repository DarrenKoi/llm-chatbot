---
tags: [concept, workflow, langgraph, authoring]
level: intermediate
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/workflow_추가_가이드.md
  - api/workflows/translator/lg_graph.py
  - devtools/scripts/new_workflow.py
  - devtools/scripts/promote.py
---

# 워크플로 작성 절차 (Workflow Authoring)

> 새 워크플로는 `devtools/workflows/` 에서 시작해 `resolve → collect_* / execute` 패턴으로 짜고, `promote` 로 운영에 반영한다.

## 왜 필요한가? (Why)

- 곧장 `api/workflows/` 에 만들면 운영 코드와 실험 코드가 섞인다.
- 워크플로 패키지를 자립적으로 만들수록 다른 사람의 코드를 건드리지 않게 된다.
- 모든 워크플로가 동일한 `resolve → collect → execute` 모양을 공유해야 디버깅·테스트·리뷰가 일관된다.
- 비슷한 다른 개념과의 차이: 일반 LangGraph 튜토리얼이 보여주는 자유로운 그래프 토폴로지와 달리, 이 저장소는 사실상 슬롯필링 패턴 하나에 수렴한다.

## 핵심 개념 (What)

### 정의

새 워크플로 작성 표준 작업 순서 (`raw/learning-logs/workflow_추가_가이드.md` §현재 저장소의 표준 작업 순서):

1. `workflow_id` 결정 (소문자 `snake_case`).
2. `python -m devtools.scripts.new_workflow <workflow_id>` 로 dev 패키지 스캐폴딩.
3. 패키지 내부 `lg_state.py` 에 `ChatState` 상속 전용 상태 정의.
4. `lg_graph.py` 에 `resolve → collect_* → execute` 패턴 구현.
5. 필요하면 dev MCP 도구 연결 (`devtools/mcp/<workflow_id>.py`).
6. `python -m devtools.workflow_runner.app` 로 멀티턴 흐름 검증.
7. 그래프 단위 + handoff 단위 테스트 추가.
8. `python -m devtools.scripts.promote <workflow_id>` 로 운영 반영.

### 관련 용어

- `workflow_id`: 디렉터리명·레지스트리 식별자·MCP 파일명·`handoff_keywords` 매칭 시 분기 대상 — 모두 같은 값.
- `resolve_node`: 현재 상태를 평가해 다음 노드를 결정. 부수효과 없이 상태만 갱신.
- `collect_*_node`: `interrupt({"reply": ...})` 로 사용자에게 질문하고 응답을 상태에 넣는 노드.
- `execute_node`: 모든 슬롯이 채워진 뒤 실제 업무를 수행하고 `END` 로 빠지는 노드.
- `last_asked_slot`: 직전에 물어본 슬롯 이름. resolve 노드가 이 값으로 분기 우선순위를 정한다.
- `pending_reply`: collect 노드에서 사용자에게 보여줄 메시지를 보관 (코드가 직접 반환할 한국어 reply).

### 시각화 / 모델

```text
                ┌────────────────────────────┐
                │       resolve_node         │
                │  (상태 평가 + 조건 분기)     │
                └──┬───────┬────────┬────────┘
                   │       │        │
            ┌──────┘       │        └──────┐
            ▼              ▼                ▼
       collect_A      collect_B         execute_node
       (interrupt)    (interrupt)       (END)
            │              │
            └──────┬───────┘
                   ▼
              resolve로 루프백
```

## 어떻게 사용하는가? (How)

### 최소 예제

```python
# api/workflows/my_workflow/lg_graph.py
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from api.workflows.my_workflow.lg_state import MyWorkflowState


def resolve_node(state: MyWorkflowState) -> dict:
    if not state.get("required_field"):
        return {"last_asked_slot": "required_field",
                "pending_reply": "필요한 정보를 알려주세요."}
    return {"last_asked_slot": ""}


def collect_node(state: MyWorkflowState) -> dict:
    user_input = interrupt({"reply": state.get("pending_reply", "")})
    return {"user_message": user_input, "last_asked_slot": "required_field"}


def execute_node(state: MyWorkflowState) -> dict:
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

`build_lg_graph()` 는 **컴파일되지 않은** `StateGraph` 빌더를 반환한다. compile 은 상위 오케스트레이터가 담당한다 (`raw/learning-logs/workflow_추가_가이드.md` §5).

### 실무 패턴

- **노드 함수는 부분 dict 만 반환**: 상태 전체를 반환하지 않는다. LangGraph 가 머지한다.
- **수집 노드 → resolve 루프백**: `add_edge("collect_*", "resolve")`. resolve 가 매번 전체 상태를 평가하므로 사용자가 한 번에 여러 정보를 주거나 순서를 건너뛰어도 자연스럽게 대응된다.
- **라우팅 함수는 부수효과 없음**: 상태를 읽기만 하고 수정은 노드가 담당.
- **라우팅 함수의 분기 우선순위** (`raw/learning-logs/workflow_추가_가이드.md` §5):
  1. 종료 조건 (`conversation_ended`) — 맨 위
  2. 명시적 슬롯 요청 (`last_asked_slot`) — LLM 이 지정한 다음 질문 존중
  3. 누락 필드 — 업무 흐름의 자연스러운 순서로
  4. 모두 채워졌을 때의 기본 실행 경로
- **interrupt 페이로드는 `{"reply": ...}`**: 오케스트레이터가 이 값을 사용자에게 보여준다. 응답 후 `Command(resume=user_input)` 으로 재개되며, 노드는 보통 `user_message` 와 `last_asked_slot` 을 함께 갱신.
- **그래프 빌드 진입 시 도구 등록**: 도구가 필요한 워크플로는 `__init__.py` 의 `build_lg_graph()` 안에서 `register_*_tools()` 를 호출 — `translator` 와 같은 패턴.

### 주의사항 / 함정

- **`workflow_id` ≠ 디렉터리명** 인 경우 레지스트리에서 혼란이 발생.
- **`get_workflow_definition()` 에서 `build_lg_graph` 누락** — callable 누락은 가장 흔한 등록 실패 원인.
- **`handoff_keywords` 를 너무 넓게 잡기** — `여행`, `계획` 처럼 단독 일반 명사는 오라우팅. 2~3 단어 표현을 우선.
- **`interrupt` 를 resolve/execute 에서 호출** — 라우팅 결정과 슬롯 수집이 섞여 디버깅 난도가 폭증. collect 전용으로 가둬 둘 것.
- **`prompts.py` 에 한국어 reply 를 섞기** — `_STOP_REPLY` 같은 코드가 직접 사용자에게 돌려주는 문자열은 노드 파일에 두고, LLM 에 들어가는 문자열만 `prompts.py` 로 — [workflow-prompting.md](workflow-prompting.md) 참고.
- **`devtools.mcp.` import 를 운영에 그대로 남기기** — `promote` 가 자동 치환하지만 다른 절대 import 는 처음부터 `api.workflows.<id>.*` 기준으로 쓸 것.
- **dev runner 검증을 건너뛰는 실수**: `python -m devtools.workflow_runner.app` 으로 첫 메시지 진입, 누락 슬롯 질문, resume, 상태 누적, 완료 후 잔여 상태 정리를 모두 확인 (`raw/learning-logs/workflow_추가_가이드.md` §8).

### 권장 체크리스트

- 새 워크플로는 `new_workflow` 로 시작.
- 전용 상태는 자기 패키지 안 `lg_state.py` 에 `ChatState` 상속.
- 상태 필드는 꼭 필요한 값만.
- 노드는 한 가지 책임만.
- `handoff_keywords` 는 좁고 구체적으로.
- dev runner 에서 멀티턴 흐름 직접 확인.
- 그래프 단위 테스트 + handoff 테스트.
- 운영 반영은 `promote`.
- 공유 파일(`api/workflows/lg_state.py`, `registry.py`)은 수정하지 않음.

## 참고 자료 (References)

- 원본 메모: [../../raw/learning-logs/workflow_추가_가이드.md](../../raw/learning-logs/workflow_추가_가이드.md)
- 관련 개념:
  - [workflow-registration.md](workflow-registration.md) — 등록 계약
  - [workflow-state-management.md](workflow-state-management.md) — 상태 분리
  - [workflow-prompting.md](workflow-prompting.md) — 프롬프트 모듈 규칙
  - [workflow-runtime-structure.md](workflow-runtime-structure.md) — 런타임 구조
- 코드 경로:
  - `api/workflows/translator/lg_graph.py`
  - `devtools/workflows/_template/`
  - `devtools/workflows/travel_planner_example/`
  - `devtools/scripts/new_workflow.py`
  - `devtools/scripts/promote.py`
