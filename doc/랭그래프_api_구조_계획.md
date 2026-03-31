# LangGraph 기반 API 구조 계획

## 1. 목적

현재 프로젝트는 `Cube -> queue -> worker -> LLM -> Cube 응답` 흐름으로 단순하게 동작한다.  
앞으로는 아래 방향을 수용할 수 있는 구조가 필요하다.

- LangGraph 기반 workflow orchestration
- 여러 업무(workflow target)를 하나의 챗봇에서 처리
- workflow 간 handoff / resume
- conditional routing
- MCP tool calling
- workflow 내부의 RAG / agent 확장

이 문서는 위 요구를 반영해 `api/` 폴더를 어떻게 나누는 것이 적절한지 정리한다.

---

## 2. 핵심 설계 원칙

### 2.1 최상위 기준은 "업무 workflow"다

이번 구조의 기준은 `chat`, `rag`, `agent` 같은 엔진 성격이 아니라 실제 업무 단위다.

즉, 처음부터 아래와 같은 workflow target을 최상위 폴더로 둔다.

- `api/workflows/general_chat/`
- `api/workflows/chart_maker/`
- `api/workflows/ppt_maker/`
- `api/workflows/at_wafer_quota/`
- `api/workflows/recipe_requests/`
- `api/workflows/common/`

이렇게 해야 각 업무가 독립적으로 진화하면서도, 필요한 경우 중간 단계에서 서로 handoff 할 수 있다.

### 2.2 RAG와 Agent는 workflow 바깥 공용 top-level이 아니라, 각 workflow 내부 capability로 둔다

이번 구조에서는 RAG와 agent를 처음부터 `api/workflows/rag/`, `api/workflows/agent/`처럼 분리하지 않는다.

대신 각 workflow가 필요로 하는 범위 안에서 자기 하위 폴더로 가진다.

예:

- `api/workflows/general_chat/rag/`
- `api/workflows/general_chat/agent/`
- `api/workflows/ppt_maker/rag/`
- `api/workflows/ppt_maker/agent/`

의미:

- `general_chat`의 retrieval 전략과 `ppt_maker`의 retrieval 전략은 다를 수 있다.
- `at_wafer_quota`의 agent loop와 `recipe_requests`의 agent loop는 필요한 tool, 정책, 종료 조건이 다를 수 있다.
- 따라서 초기 설계 기준은 "공용 rag/agent"가 아니라 "업무별 rag/agent"가 더 자연스럽다.

단, 여러 workflow에서 동일한 로직을 실제로 공유하게 되면 그때 `common/` 또는 별도 infra/service 계층으로 승격한다.

### 2.3 `common`은 shared sub-workflow / shared node 모음이다

업무 workflow가 여러 개여도, 아래 기능은 공통으로 재사용될 가능성이 높다.

- 사용자 확인
- 부서 / 권한 확인
- 입력 확인 / 최종 confirm
- 취소 / 재개
- 사람 상담 전환
- 첨부파일 수집

이런 것은 `api/workflows/common/` 아래에 둔다.

즉 `common`은 보조 helper가 아니라, 다른 workflow에서 호출 가능한 shared workflow 집합이다.

예:

- `recipe_requests -> common.verify_user -> recipe_requests 복귀`
- `at_wafer_quota -> common.confirm -> submit`
- `ppt_maker -> common.collect_attachment -> outline 생성`

### 2.4 Cube와 queue 계층은 얇게 유지한다

현재 `cube` 계층은 HTTP ingress, payload parsing, queue 적재, worker 실행에 강점이 있다.
LangGraph 도입 후에도 `api/cube/`는 이 책임만 유지하고, 실제 업무 판단은 `workflows` 계층으로 옮긴다.

즉 `cube/service.py`는 다음만 담당한다.

- payload 해석
- empty / wake-up / duplicate 처리
- queue 적재 및 worker 실행
- orchestrator 호출
- 최종 Cube 응답 전송

실제 "지금 어떤 workflow를 타는가", "어느 node에 있는가", "다른 workflow로 handoff 할 것인가"는 `workflows/orchestrator.py`가 담당한다.

### 2.5 workflow state는 대화 히스토리와 분리해서 관리한다

현재 `conversation_service.py`는 메시지 히스토리만 저장한다.
하지만 multi-workflow 구조에서는 아래 정보가 별도로 필요하다.

- 현재 active workflow
- 현재 node
- workflow별 수집 데이터
- handoff 후 돌아올 위치
- workflow 상태 (`active`, `waiting_user_input`, `completed`, `cancelled`)

즉, 대화 메시지 저장만으로는 부족하고, workflow state 저장소가 필요하다.

### 2.6 LLM은 controller가 아니라 node 내부의 도구다

LLM은 workflow 전체를 자유롭게 결정하는 controller가 아니라, 각 node 안에서 쓰이는 컴포넌트여야 한다.

예:

- 사용자 입력에서 슬롯 추출
- 자연스러운 다음 질문 생성
- slide 문안 초안 생성
- quota 조회 결과 설명

반면 아래는 가능하면 코드와 state로 관리한다.

- 현재 workflow 판정
- handoff / resume
- business rule branch
- 외부 시스템 결과 기반 분기

### 2.7 workflow별 확장 방식은 달라도, orchestration contract는 공통이어야 한다

`general_chat`, `ppt_maker`, `at_wafer_quota`는 성격이 다르다.

- `general_chat`: 자유 대화 중심
- `chart_maker`: 산출물 생성 중심
- `ppt_maker`: 장기적 iterative workflow
- `at_wafer_quota`: 조회 + 분기 + 신청
- `recipe_requests`: step-by-step slot filling

하지만 orchestrator가 다루는 공통 contract는 같아야 한다.

- 현재 state 로드
- 현재 node 실행
- `NodeResult` 수신
- state 갱신
- reply 반환
- handoff / resume 처리

---

## 3. 권장 `api/` 폴더 구조

```text
api/
  __init__.py
  blueprint_loader.py
  config.py
  conversation_service.py       # 대화 히스토리 read model 용도로 유지 가능

  cube/
    __init__.py
    client.py
    router.py
    service.py
    worker.py
    payload.py
    queue.py
    models.py

  workflows/
    __init__.py
    orchestrator.py
    registry.py
    models.py
    state_service.py

    common/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py

    general_chat/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py
      rag/
        __init__.py
        retriever.py
        context_builder.py
      agent/
        __init__.py
        planner.py
        executor.py

    chart_maker/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py
      rag/
        __init__.py
      agent/
        __init__.py

    ppt_maker/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py
      rag/
        __init__.py
      agent/
        __init__.py

    at_wafer_quota/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py
      rag/
        __init__.py
      agent/
        __init__.py

    recipe_requests/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py
      rag/
        __init__.py
      agent/
        __init__.py

  llm/
    __init__.py
    registry.py
    prompt/
      __init__.py
      system.py

  mcp/
    __init__.py
    client.py
    registry.py
    models.py
    errors.py
    cache.py
    tool_adapter.py
    tool_selector.py
    executor.py

  archive/
    __init__.py
    service.py
    extractor.py
    opensearch_client.py
    models.py

  utils/
    ...
```

---

## 4. 폴더별 책임

### 4.1 `api/cube/`

Cube 연동 경계다.

주요 책임:

- HTTP endpoint 수신
- payload parsing
- wake-up / empty / duplicate 처리
- Redis queue 적재
- worker 루프 실행
- orchestrator 호출
- 최종 Cube 응답 전송

즉, `cube/service.py`는 business workflow 자체를 모르고, `workflows/orchestrator.py`를 호출해 결과를 받아 전달하는 thin transport 계층이어야 한다.

### 4.2 `api/workflows/`

multi-workflow orchestration의 중심이다.

주요 책임:

- workflow registry
- active workflow 선택
- workflow state load / save
- node 실행
- handoff / resume
- workflow 종료 / 재개

즉, 기존의 "chat service가 직접 답변 생성" 구조를 "orchestrator가 workflow 실행" 구조로 바꾼다.

### 4.3 `api/workflows/common/`

shared sub-workflow 집합이다.

예상 책임:

- `verify_user`
- `confirm`
- `cancel_or_resume`
- `human_handoff`
- `collect_attachment`

각 업무 workflow는 필요 시 `common`으로 handoff 했다가 원래 workflow로 복귀할 수 있다.

### 4.4 `api/workflows/general_chat/`

자유 대화와 일반 질의응답을 담당한다.

예상 책임:

- 일반 대화 응답
- broad intent classification
- 가벼운 retrieval
- tool-assisted answer
- 다른 업무 workflow로 진입 전 초기 라우팅 보조

이 workflow는 fallback 역할도 할 수 있다.

### 4.5 `api/workflows/chart_maker/`

chart 생성 관련 요청을 담당한다.

예상 책임:

- 사용자가 원하는 chart 종류 파악
- 필요한 데이터 / 축 / 범례 정보 수집
- chart specification 생성
- chart 초안 생성
- 수정 지시 반영

### 4.6 `api/workflows/ppt_maker/`

PowerPoint 작성 지원 workflow다.

예상 책임:

- 목적 / 청중 / 발표 길이 파악
- source content 수집
- outline 생성
- slide별 문안 생성
- 수정 / 재구성
- 최종 deck 생성 보조

이 workflow는 step-by-step 진행과 iterative revision이 중요하다.

### 4.7 `api/workflows/at_wafer_quota/`

AT wafer quota 조회 및 후속 액션을 담당한다.

예상 책임:

- quota 조회
- 잔여 quota 설명
- 분기:
  - quota가 충분하면 wafer testing 요청
  - quota가 부족하면 borrow 절차 진입
- 최종 확인 및 제출

이 workflow는 외부 시스템 조회와 business rule branch가 강한 영역이다.

### 4.8 `api/workflows/recipe_requests/`

recipe creation / request workflow다.

예상 책임:

- 요청 목적 파악
- step-by-step 정보 수집
- 누락 정보 재질문
- 입력 요약 및 사용자 확인
- 최종 제출

이 workflow는 form-like slot filling 성격이 강하다.

### 4.9 workflow 내부의 `rag/`, `agent/`

각 workflow 아래의 `rag/`, `agent/`는 그 workflow 전용 capability를 둔다.

예:

- `ppt_maker/rag/`: 사용자가 준 문서, 템플릿, 과거 deck에서 문맥 추출
- `general_chat/rag/`: 일반 사내 지식 검색
- `at_wafer_quota/agent/`: quota 확인 후 필요한 시스템 조회/도구 호출 loop

원칙:

- workflow에 강하게 종속된 retrieval / agent 로직은 그 workflow 내부에 둔다.
- 여러 workflow가 공유하게 되면 그때 `common/` 또는 별도 service 계층으로 승격한다.

### 4.10 `api/llm/`

모델 인스턴스를 생성·관리하는 레지스트리 계층이다.

주요 책임:

- 모델 목록 관리
- 모델별 설정 관리
- task / workflow / node 기준 모델 선택
- `ChatOpenAI` 인스턴스 반환

### 4.11 `api/mcp/`

MCP tool calling 인프라 계층이다.

주요 책임:

- 서버 레지스트리
- tool 목록 조회 및 캐시
- schema 변환
- tool 실행 라우팅
- timeout / exception 정규화

### 4.12 `api/archive/`

완료된 대화나 workflow 결과를 아카이빙하는 계층이다.

주요 책임:

- 대화 / 결과 메타데이터 추출
- OpenSearch 인덱싱
- 품질 개선용 분석 데이터 축적

---

## 5. orchestration 모델

### 5.1 기본 흐름

```text
Cube message 수신
  -> cube/service.py
  -> workflows/orchestrator.py
  -> active workflow / node 결정
  -> node 실행
  -> NodeResult 반환
  -> state 저장
  -> Cube 응답 전송
```

### 5.2 workflow state 예시

```python
{
  "user_id": "u123",
  "workflow_id": "at_wafer_quota",
  "node_id": "decide_next_action",
  "status": "active",
  "data": {
    "quota_total": 100,
    "quota_remaining": 12,
    "requested_amount": 20
  },
  "stack": [
    {
      "workflow_id": "at_wafer_quota",
      "node_id": "confirm_submission"
    }
  ]
}
```

### 5.3 handoff / resume

`stack`은 다른 workflow를 호출했다가 돌아오기 위한 정보다.

예:

```text
recipe_requests.ask_required_info
  -> common.verify_user
  -> recipe_requests.confirm_inputs
```

또는:

```text
at_wafer_quota.fetch_quota
  -> quota 부족
  -> at_wafer_quota.borrow_quota
  -> common.confirm
  -> at_wafer_quota.submit
```

### 5.4 새 요청 라우팅

새 사용자 요청이 오면 아래 순서로 처리한다.

1. active workflow가 있으면 우선 이어서 진행
2. active workflow가 없으면 classifier 또는 rule 기반으로 target workflow 결정
3. 해당 workflow의 entry node부터 시작

즉, "챗봇은 하나"지만 "업무 workflow는 여러 개"인 구조다.

---

## 6. workflow 패키지 내부 템플릿

각 업무 workflow는 가능하면 동일한 파일 구성을 따른다.

### 6.1 `graph.py`

- LangGraph 정의
- state transition 연결
- entry / end node 선언

### 6.2 `state.py`

- workflow 전용 state 정의
- 공통 필드 + 업무별 필드

예:

- `ppt_maker`: audience, tone, outline, slide_drafts
- `recipe_requests`: recipe_type, material_info, process_conditions
- `at_wafer_quota`: quota_total, quota_remaining, requested_amount

### 6.3 `nodes.py`

- node 함수 구현
- 가능하면 side effect와 LLM 호출을 명확히 분리

### 6.4 `routing.py`

- conditional branch 로직
- 다음 node 선택 로직
- handoff 조건 정의

### 6.5 `prompts.py`

- workflow 전용 prompt template
- node별 system / developer prompt 모음

### 6.6 `rag/`

- 이 workflow에 특화된 검색 로직
- retriever / context builder / source adapter

### 6.7 `agent/`

- 이 workflow에 특화된 planning / execution loop
- tool selection
- termination condition

---

## 7. 초기 구현 권장 범위

처음부터 모든 workflow를 다 구현할 필요는 없다.
폴더는 미리 만들어도 되지만, 실제 로직은 우선순위 기반으로 들어가는 것이 맞다.

### 7.1 먼저 만드는 것

- `api/workflows/orchestrator.py`
- `api/workflows/registry.py`
- `api/workflows/models.py`
- `api/workflows/state_service.py`
- `api/workflows/common/`
- `api/workflows/general_chat/`
- `api/llm/`
- `api/mcp/`

### 7.2 다음 순서

- `api/workflows/recipe_requests/`
- `api/workflows/at_wafer_quota/`
- `api/workflows/ppt_maker/`
- `api/workflows/chart_maker/`

이 순서가 좋은 이유:

- 먼저 orchestrator와 공통 contract를 고정할 수 있다.
- 이후 업무 workflow를 하나씩 붙여도 구조가 흔들리지 않는다.

---

## 8. 예상 인터페이스

### 8.1 `api/workflows/models.py`

```python
from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowStatus = Literal["active", "waiting_user_input", "completed", "cancelled"]
NodeAction = Literal["reply", "handoff", "resume", "complete", "wait"]


@dataclass
class WorkflowState:
    user_id: str
    workflow_id: str
    node_id: str
    status: WorkflowStatus = "active"
    data: dict[str, Any] = field(default_factory=dict)
    stack: list[dict[str, str]] = field(default_factory=list)


@dataclass
class NodeResult:
    action: NodeAction
    reply: str = ""
    next_node_id: str | None = None
    next_workflow_id: str | None = None
    data_updates: dict[str, Any] = field(default_factory=dict)
```

### 8.2 `api/workflows/orchestrator.py`

```python
def handle_message(incoming: CubeIncomingMessage, attempt: int = 0) -> str:
    """
    Cube worker가 호출하는 workflow 진입점.
    active workflow를 이어서 실행하거나, 새 workflow를 시작한다.
    """
    ...
```

### 8.3 `api/workflows/registry.py`

```python
def get_workflow(workflow_id: str):
    """등록된 workflow graph / entrypoint를 반환한다."""
    ...
```

### 8.4 `api/workflows/state_service.py`

```python
def load_state(user_id: str) -> WorkflowState | None:
    ...

def save_state(state: WorkflowState) -> WorkflowState:
    ...

def clear_state(user_id: str) -> None:
    ...
```

---

## 9. 마이그레이션 경로

현재 `cube/service.py`의 `process_incoming_message`는 아래 흐름이다.

```text
1. wake-up 판정
2. history 조회 + user message 저장
3. generate_reply (LLM)
4. assistant message 저장
5. send_multimessage
```

변경 후 흐름은 아래와 같다.

```text
1. wake-up / empty / duplicate 판정
2. workflows/orchestrator.py 호출
3. active workflow 또는 새 workflow 결정
4. 해당 workflow node 실행
5. state 저장
6. reply 반환
7. cube/service.py가 send_multimessage 전송
8. archive/service.py 비동기 호출
```

즉, 기존 direct LLM 호출 위치를 orchestrator 진입점으로 바꾸는 것이 핵심이다.

---

## 10. 최종 권장안

이번 구조의 핵심은 다음이다.

- top-level workflow는 업무 단위로 나눈다
- `general_chat`, `chart_maker`, `ppt_maker`, `at_wafer_quota`, `recipe_requests`, `common`을 기준으로 간다
- RAG와 agent는 각 workflow 내부 서브폴더로 둔다
- `common`은 shared sub-workflow 집합으로 사용한다
- Cube는 thin transport 계층으로 유지한다
- workflow state는 대화 히스토리와 분리해 저장한다

즉, 이제의 기준은:

- `chat / rag / agent` 중심 구조가 아니라
- `업무 workflow + 그 내부 capability` 중심 구조다

이 방식이 실제 업무 확장, coworker별 workflow 추가, 중간 handoff, 장기 유지보수에 가장 잘 맞는다.
