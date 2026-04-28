# LangGraph 워크플로 핸드북

> 최종 업데이트: 2026-04-28

이 문서는 `shared_docs/`에서 팀원이 공통으로 참고할 수 있도록, 현재 저장소의 워크플로 관련 문서를 하나로 정리한 통합 안내서입니다.
대상 원문은 `doc/code_explain/workflows.md`, `doc/guideline/workflow_등록_가이드.md`, `doc/guideline/workflow_추가_가이드.md`, `doc/guideline/workflow_상태_관리_가이드.md`이며, 실제 코드 구조에 맞게 중복과 오래된 설명을 정리했습니다.

> ⚠️ **최근 변경 (2026-04-28)** — MCP 패키지가 `api/mcp/` → `api/mcp_client/`, `devtools/mcp/` → `devtools/mcp_client/` 로 정리되었고 호환성 shim은 제거되었습니다. 본 문서의 모든 예시와 promote 동작 설명은 새 경로 기준입니다. 이전 경로(`api.mcp`, `devtools.mcp`)는 더 이상 존재하지 않습니다.

## 1. 현재 런타임 구조

이 저장소의 워크플로 구조는 “워크플로마다 독립 엔진을 따로 돌리는 방식”이 아니라, `start_chat`을 루트로 둔 하나의 LangGraph 런타임 안에 업무형 서브그래프를 붙이는 구조입니다.

메시지 처리의 핵심 경로는 아래와 같습니다.

1. Cube 입력이 `api/cube/router.py`로 들어옵니다.
2. 큐와 워커를 거쳐 `api/workflows/lg_orchestrator.py`의 `handle_message()`가 호출됩니다.
3. 오케스트레이터는 `api/workflows/start_chat/lg_graph.py`의 루트 그래프를 한 번 컴파일해 재사용합니다.
4. 루트 그래프는 먼저 `start_chat` 흐름을 실행합니다.
5. 일반 대화면 `retrieve_context -> generate_reply`로 끝납니다.
6. 특정 업무 의도가 감지되면 `translator` 같은 서브그래프로 분기합니다.
7. 서브그래프가 추가 입력을 요구하면 `interrupt()`로 멈추고, 다음 사용자 메시지에서 `Command(resume=...)`로 이어서 실행합니다.

중요한 점은 `start_chat`이 루트 그래프이지만 워크플로 레지스트리에는 등록되지 않는다는 점입니다. 레지스트리에는 handoff 대상 워크플로만 등록되고, 루트 진입점은 `lg_orchestrator`가 직접 `start_chat` 그래프를 사용합니다.

## 2. LangGraph가 맡는 역할

### 상태 머신

각 워크플로는 `StateGraph`로 정의합니다.

- 루트 그래프: `api/workflows/start_chat/lg_graph.py`
- 서브그래프 예시:
  - `api/workflows/translator/lg_graph.py`

노드는 상태를 읽고, 변경할 필드만 담은 `dict`를 반환합니다.
즉, 함수 호출 순서보다 상태 전이 규칙이 중심입니다.

### 멀티턴 대화 유지

이 저장소에서 LangGraph를 쓰는 가장 큰 이유는 멀티턴 업무 흐름을 자연스럽게 이어가기 쉽기 때문입니다.

- `interrupt({"reply": ...})`
  현재 턴에서 사용자에게 질문을 던지고 실행을 멈춥니다.
- `Command(resume=user_input)`
  다음 사용자 입력으로 멈춘 지점부터 다시 이어갑니다.
- `checkpointer`
  중간 상태를 thread 단위로 저장합니다.

이 패턴은 `translator`에서 가장 분명하게 보입니다.

### thread 단위 지속성

`api/workflows/langgraph_checkpoint.py`는 thread 식별과 체크포인터 생성을 담당합니다.

- thread id 형식: `user_id::channel_id`
- Mongo 설정이 있으면 `MongoDBSaver`
- 아니면 `MemorySaver`

현재 production에서는 워크플로별 thread를 따로 만들지 않고 “사용자 + 채널” 기준으로 하나의 대화 thread를 유지합니다.

## 3. 워크플로 패키지 계약

새 워크플로를 production에 넣으려면 패키지 단위 계약을 맞춰야 합니다.

### 기본 파일 구조

현재 권장 구조는 아래와 같습니다.

```text
api/workflows/<workflow_id>/
├── __init__.py
├── lg_graph.py
├── lg_state.py
├── nodes.py          # 선택
├── prompts.py        # 선택
└── tools.py          # 선택
```

핵심은 `state.py`가 아니라 `lg_state.py`입니다.
현재 공통 상태는 `api/workflows/lg_state.py`의 `ChatState`에만 두고, 워크플로 전용 상태는 각 패키지의 `lg_state.py`에 둡니다.

### `__init__.py` 등록 계약

레지스트리는 각 패키지의 `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`을 읽어 워크플로를 발견합니다.

가장 단순한 예시는 아래와 같습니다.

```python
def build_lg_graph():
    from .lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "sample_flow",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": ("샘플 업무", "sample flow"),
    }
```

현재 기준에서 중요한 필드는 아래와 같습니다.

- `workflow_id`
  최종 등록 이름입니다.
- `build_lg_graph`
  실제 LangGraph 빌더를 반환하는 callable이어야 합니다.
- `handoff_keywords`
  `start_chat`가 이 워크플로로 넘길지 판단하는 기준입니다.
- `tool_tags`
  선택 사항이며, 도구 관련 분류에 사용됩니다.

주의할 점:

- `state_cls`는 더 이상 필수 계약이 아니며, 레지스트리 정규화 과정에서 제거됩니다.
- `workflow_id`는 중복되면 런타임 예외가 납니다.
- 디렉터리명, `workflow_id`, dev MCP 파일명, 운영 MCP 파일명을 같은 값으로 맞추는 편이 안전합니다.

### 상태 정의 원칙

공유 기본 상태는 `ChatState` 하나입니다.

```python
from api.workflows.lg_state import ChatState  # legacy: devtools에서는 mirror 사본 사용 예정


class MyWorkflowState(ChatState, total=False):
    source_text: str
    target_language: str
    last_asked_slot: str
```

현재 상태 설계 규칙은 아래와 같습니다.

- 공유 기본 상태 `ChatState`는 `api/workflows/lg_state.py`에 둡니다.
- `devtools/`에서 사용할 때는 격리 정책에 따라 별도 mirror 사본(`devtools/workflows/lg_state.py`, 도입 예정)을 사용해야 합니다 — 자세한 내용은 [`workflow_catalog.md`](./workflow_catalog.md) §3.5 참조.
- 워크플로 전용 상태는 각 패키지 안의 `lg_state.py`에 둡니다.
- 특정 워크플로에만 필요한 필드를 `ChatState`에 직접 추가하지 않습니다 — 추가가 필요하면 `api/`와 `devtools/` 양쪽 사본을 함께 업데이트해 mirror를 깨지 않습니다.
- 상태 필드는 여러 턴에 걸쳐 다시 참조할 값만 남깁니다.
- `TypedDict(total=False)`를 유지해 초기 상태에서 선택 필드를 비워 둘 수 있게 합니다.

## 4. 워크플로 등록과 handoff

### 레지스트리 발견 규칙

`api/workflows/registry.py`의 `discover_workflows()`는 `api.workflows` 아래 서브패키지를 스캔합니다.

자동 발견 규칙은 아래와 같습니다.

- 디렉터리가 패키지여야 합니다.
- 패키지 이름이 `_`로 시작하면 건너뜁니다.
- `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`이 있어야 합니다.
- `build_lg_graph`가 callable이어야 합니다.

즉, 중앙 목록 파일에 수동 등록하는 구조가 아닙니다.

### `handoff_keywords`의 역할

`start_chat` 루트 그래프는 `list_handoff_workflows()` 결과를 읽어 handoff 대상 워크플로를 붙입니다.
`handoff_keywords`가 비어 있지 않은 워크플로만 자동 라우팅 대상으로 들어갑니다.

현재 분류 방식은 단순 문자열 포함 검사이므로 키워드 설계가 매우 중요합니다.

좋은 키워드 원칙:

- 실제 사용자 발화에 자주 등장하는 표현을 사용합니다.
- 다른 워크플로와 겹치지 않는 표현을 고릅니다.
- 업무 목적이 바로 드러나는 표현을 씁니다.
- 한국어와 영어 요청이 모두 들어오면 두 언어 표현을 함께 둡니다.

피해야 할 예:

- `도움`
- `계획`
- `문서`
- `분석`

이런 단어는 범위가 넓어 오라우팅을 일으키기 쉽습니다.

### 루트 그래프의 handoff 방식

`api/workflows/start_chat/lg_graph.py`는 아래 순서로 동작합니다.

1. `list_handoff_workflows()`로 handoff 대상 워크플로를 읽습니다.
2. 각 워크플로의 `build_lg_graph()`를 호출해 서브그래프를 붙입니다.
3. 사용자 메시지를 소문자로 바꿉니다.
4. `handoff_keywords` 중 하나라도 포함되면 해당 `workflow_id`로 분기합니다.
5. 어떤 키워드도 맞지 않으면 일반 `start_chat` 응답 경로로 남습니다.

따라서 현재 구조에서 “등록”은 사실상 `레지스트리 계약 + handoff 키워드 설계`의 조합입니다.

## 5. 새 워크플로를 만드는 표준 절차

현재 저장소의 표준 작업 순서는 아래와 같습니다.

1. `workflow_id`를 정합니다.
2. `devtools/scripts/new_workflow.py`로 dev 워크플로를 생성합니다.
3. 패키지 안의 `lg_state.py`에 `ChatState`를 상속한 전용 상태를 정의합니다.
4. `lg_graph.py`에 resolve-collect-execute 패턴으로 그래프를 구현합니다.
5. 필요하면 dev MCP 도구를 연결합니다.
6. dev runner에서 대화 흐름과 상태 전이를 검증합니다.
7. 테스트를 추가하고 실행합니다.
8. `devtools/scripts/promote.py`로 운영 경로에 반영합니다.

### 1. `workflow_id` 설계

`workflow_id`는 아래 항목의 기준점입니다.

- 워크플로 디렉터리 경로
- 레지스트리 식별자
- `start_chat` handoff 대상 이름
- dev MCP 파일명
- 운영 MCP 파일명

처음부터 소문자 `snake_case`로 정하고, 업무 단위가 드러나는 이름을 쓰는 편이 좋습니다.

좋은 예:

- `translator`
- `invoice_summary`
- `incident_summary`

피해야 할 예:

- `test`
- `temp_work`
- `newflow`
- `myWorkflow`

### 2. devtools에서 스캐폴딩

새 워크플로는 바로 `api/workflows/`에 만들지 않고 `devtools/workflows/`에서 먼저 시작합니다.

```bash
python -m devtools.scripts.new_workflow sample_flow
```

현재 템플릿은 아래 파일을 생성합니다.

```text
devtools/workflows/sample_flow/
├── __init__.py
├── lg_graph.py
└── lg_state.py

devtools/mcp_client/sample_flow.py
```

### 3. 그래프 구현 패턴

현재 저장소에서 가장 많이 쓰는 패턴은 `resolve -> collect -> execute` 흐름입니다.

- `resolve`
  현재 입력과 기존 상태를 보고 다음 액션을 정합니다.
- `collect_*`
  누락 슬롯이 있으면 사용자에게 물어보는 노드입니다.
- `execute`
  필요한 정보가 모두 모였을 때 실제 도구 호출이나 최종 응답 생성을 수행합니다.

번역 워크플로 예시는 아래 식으로 읽을 수 있습니다.

```text
resolve
  ├─ source_text 없음 -> collect_source_text
  ├─ target_language 없음 -> collect_target_language
  └─ 모두 있음 -> translate
```

`devtools/workflows/travel_planner_example/`는 같은 패턴을 더 많은 상태 필드와 분기 조건으로 확장한 참고 예제입니다.

### 4. 노드와 엣지 작성 원칙

노드 함수는 상태를 읽고, 바꿀 필드만 `dict`로 반환합니다.

```python
def resolve_node(state: MyWorkflowState) -> dict:
    if state.get("conversation_ended"):
        return {}
    return {"last_asked_slot": "target_language"}
```

조건부 분기는 `add_conditional_edges()`로 구현합니다.

```python
builder.add_conditional_edges("resolve", _route_after_resolve)
```

라우팅 함수는 다음 노드 이름 문자열 또는 `END`를 반환합니다.

### 5. 멀티턴은 `interrupt/resume`

이 저장소는 누락 슬롯 수집을 위해 임의 세션 저장 로직을 덧붙이는 방식보다 LangGraph의 `interrupt/resume` 패턴을 기본으로 사용합니다.

권장 방식:

- 사용자에게 질문해야 할 때 `interrupt({"reply": ...})`
- 다음 사용자 입력에서 `Command(resume=...)`

규모가 커지면 interrupt payload를 아래처럼 조금 더 구조화해 두는 편이 좋습니다.

- `reply`
- `expected_input`
- `missing_slot`
- `workflow_id`
- `examples`

현재 런타임은 `reply`만 있어도 동작하지만, UI와 로그 일관성을 생각하면 위 형식이 더 확장성 있습니다.

## 6. 도구 연동과 MCP

워크플로가 외부 도구를 써야 하면 워크플로 등록만으로는 충분하지 않습니다.

예를 들어 `translator`는 `build_lg_graph()` 경로에서 도구 등록 함수를 먼저 호출합니다.

```python
def build_lg_graph():
    from api.workflows.translator.lg_graph import build_lg_graph as builder
    from api.workflows.translator.tools import register_translator_tools

    register_translator_tools()
    return builder()
```

dev 단계에서는 `devtools/mcp_client/<workflow_id>.py`를 사용하고, promotion 시 `api/mcp_client/`로 옮깁니다.

도구 연동 시 기억할 점:

- 워크플로 등록과 도구 등록은 별도 계층입니다.
- 도구 등록 함수 호출이 빠지면 그래프는 떠도 실행 중 필요한 도구가 비어 있을 수 있습니다.
- `tool_id`는 `<workflow_id>.<tool_id>` 같은 네이밍 규칙을 두는 편이 안전합니다.
- 전역 레지스트리 충돌과 테스트 간 상태 오염을 의식해야 합니다.

## 7. devtools와 운영 반영

dev 환경도 운영과 같은 자동 발견 메커니즘을 사용합니다.

- `devtools.workflow_runner.dev_orchestrator`는 `discover_workflows(package_name="devtools.workflows")`를 호출합니다.
- 즉, dev와 prod는 “중앙 목록 수동 수정”이 아니라 “패키지 계약을 맞추면 자동 발견”이라는 동일한 모델을 공유합니다.

운영 반영은 아래 명령으로 진행합니다.

```bash
python -m devtools.scripts.promote sample_flow
```

`promote` 스크립트는 아래 작업을 수행합니다.

1. dev 워크플로 패키지를 `api/workflows/`로 복사합니다.
2. 대응하는 dev MCP 모듈을 `api/mcp_client/`로 복사합니다.
3. `devtools.mcp_client.` import를 `api.mcp_client.`로 치환합니다.
4. import 검증을 수행합니다.
5. 검증이 통과하면 dev 원본을 삭제합니다.

즉, 현재 권장 반영 경로는 “수동 복사”가 아니라 “복사 + import 치환 + 검증”까지 포함된 promotion입니다.

## 8. 테스트와 검증 포인트

워크플로를 추가할 때는 최소한 아래를 확인하는 편이 좋습니다.

- 첫 입력만으로 완료되는 경로가 정상 동작하는지 확인합니다.
- 누락 슬롯이 있을 때 interrupt가 걸리는지 확인합니다.
- 다음 사용자 입력으로 resume이 정상 동작하는지 확인합니다.
- 레지스트리에서 `workflow_id`를 정상 발견하는지 확인합니다.
- 루트 `start_chat`에서 handoff가 기대대로 동작하는지 확인합니다.

테스트는 두 층으로 나눠 생각하면 유지보수가 쉽습니다.

- 그래프 단위 테스트
  node, edge, interrupt 동작 검증
- 오케스트레이터 단위 테스트
  루트 진입, handoff, resume, reply extraction 검증

## 9. 규모가 커질 때 주의할 점

현재 구조는 워크플로 수가 많지 않을 때 실용적입니다.
하지만 수가 늘어나면 아래 지점들이 병목이 됩니다.

### 키워드 기반 handoff 충돌

워크플로 수가 늘면 아래 문제가 커집니다.

- 키워드 중복
- 표현 다양성 증가
- 한국어/영어 혼합 발화 처리 한계
- 일반 대화와 업무형 발화 경계 모호성

규모가 커지면 아래 같은 보완이 필요합니다.

- workflow별 우선순위 규칙
- score 기반 router
- 소형 LLM 또는 분류 모델 기반 intent router
- 1차 coarse routing 후 2차 domain routing

### 루트 그래프 비대화

현재 `start_chat` 빌더는 handoff 가능한 모든 서브그래프를 루트에 붙입니다.
워크플로가 많아지면 그래프 컴파일 시간, 메모리 사용량, 디버깅 난도가 함께 올라갑니다.

확장 시 권장 방향:

1. `start_chat`은 얇은 router graph로 유지합니다.
2. 업무 도메인별 상위 그래프를 둡니다.
3. 각 도메인 아래에서 세부 workflow를 다시 라우팅합니다.
4. 무거운 그래프는 lazy compile 또는 별도 실행 경계로 분리합니다.

### 전역 도구 등록 충돌

tool namespace가 커질수록 아래 문제가 생기기 쉽습니다.

- `tool_id` 충돌
- 비슷한 도구의 중복 등록
- 테스트 간 전역 상태 오염

도구 네이밍 규칙과 fixture 초기화 규칙을 같이 문서화해 두는 편이 좋습니다.

## 10. 실무 체크리스트

새 워크플로를 추가할 때는 아래를 먼저 확인합니다.

1. 이 워크플로가 정말 루트 그래프의 handoff 대상이어야 하는지 결정합니다.
2. `handoff_keywords`만으로 안정적으로 라우팅 가능한지 검토합니다.
3. 멀티턴이라면 `interrupt()/resume` 지점을 먼저 설계합니다.
4. 공통 상태와 로컬 상태를 분리합니다.
5. 도구가 필요하면 등록 함수 호출 위치와 `tool_id` 충돌을 확인합니다.
6. 그래프 단위 테스트와 루트 handoff 테스트를 같이 추가합니다.
7. devtools에서 검증한 뒤 promotion으로 운영 반영합니다.

## 11. 한 줄 요약

현재 저장소의 LangGraph 구조는 “`start_chat` 루트 그래프 + 업무별 서브그래프 + checkpoint 기반 interrupt/resume” 모델입니다.
새 워크플로는 `devtools`에서 시작해 패키지 계약, 상태 분리, 키워드 설계, 도구 등록, 테스트를 맞춘 뒤 운영으로 승격하는 방식으로 다루는 것이 가장 안전합니다.
