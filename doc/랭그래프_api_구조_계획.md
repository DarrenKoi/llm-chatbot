# LangGraph 기반 API 구조 계획

## 1. 목적

현재 프로젝트는 `Cube -> queue -> worker -> LLM -> Cube 응답` 흐름으로 단순하게 동작한다.  
앞으로는 아래 방향을 수용할 수 있는 구조가 필요하다.

- LangGraph 기반 workflow orchestration
- conditional routing
- MCP tool calling
- 이후 RAG workflow 추가
- 이후 Agent workflow 추가

이 문서는 위 요구를 반영해 `api/` 폴더를 어떻게 나누는 것이 적절한지 정리한다.

---

## 2. 핵심 설계 원칙

### 2.1 유스케이스와 workflow 구현을 분리한다

`chat`은 "채팅 요청을 시스템이 어떻게 처리하는가"를 담당하는 유스케이스 계층이다.  
`workflows/chat`은 "그 채팅 요청 내부를 LangGraph로 어떻게 흘릴 것인가"를 담당하는 구현 계층이다.

즉:

- `api/chat/`: 애플리케이션 계층
- `api/workflows/chat/`: LangGraph 구현 계층

이렇게 나누면 나중에 workflow 엔진을 바꾸더라도 `chat.service` 진입점은 유지할 수 있다.

### 2.2 MCP는 처음부터 확장형 구조로 둔다

초기에는 몇 개의 MCP tool만 붙이더라도, 이후에는 MCP 서버 수가 늘어날 가능성이 높다.  
따라서 tool calling은 단순 helper가 아니라 별도 인프라 계층으로 분리한다.

즉:

- `api/mcp/`: MCP 서버 레지스트리, tool 목록 캐시, schema 변환, tool 실행 라우팅 담당

### 2.3 RAG와 Agent는 처음부터 모두 workflow로 만들지 않는다

RAG와 Agent는 나중에 필요해질 수 있지만, 처음부터 무조건 독립 workflow로 나누는 것은 과하다.  
초기에는 `chat` workflow 안에서 node 수준으로 호출하고, 다단계 graph가 필요해질 때만 `workflows/rag`, `workflows/agent`로 승격한다.

즉:

- 단순 retrieval 호출: `api/rag/`
- 독립적인 RAG subgraph: `api/workflows/rag/`
- 단순 agent branch: `api/workflows/chat/` 내부
- 독립적인 agent loop: `api/workflows/agent/`

### 2.4 Cube와 queue 계층은 얇게 유지한다

현재 `cube` 계층은 HTTP ingress, payload parsing, queue 적재, worker 실행에 강점이 있다.
LangGraph 도입 후에도 `api/cube/`는 이 책임만 유지하고, 실제 대화 판단은 `chat`과 `workflows`로 옮긴다.

단, **Cube 응답 전송은 `cube/service.py`가 담당한다.**
`chat/service.py`는 최종 reply 문자열을 반환하고, `cube/service.py`가 이를 받아서 `send_multimessage`로 전달한다.
이렇게 하면 `chat/` 계층은 Cube를 전혀 알 필요가 없다.

### 2.5 LLM 계층은 LangChain 모델 제공자로 사용한다

사내 LLM은 모두 OpenAI-compatible endpoint이므로 `langchain-openai`의 `ChatOpenAI`를 사용한다.
`api/llm/`은 모델 인스턴스를 생성해 반환하는 **모델 레지스트리** 역할을 한다.

- 모델별 설정(base_url, api_key, temperature 등)을 관리
- task나 조건에 따라 적절한 모델을 선택할 수 있는 인터페이스 제공
- workflow의 각 node가 필요한 모델을 registry에서 가져다 쓰는 구조

기존 `llm/service.py`의 raw `httpx` 호출은 `ChatOpenAI`로 대체된다.

---

## 3. 권장 `api/` 폴더 구조

```text
api/
  __init__.py
  blueprint_loader.py
  config.py
  conversation_service.py

  cube/
    __init__.py
    client.py
    router.py
    service.py
    worker.py
    payload.py
    queue.py
    models.py

  chat/
    __init__.py
    service.py
    models.py
    history.py

  workflows/
    chat/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py
      prompts.py

    rag/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py

    agent/
      __init__.py
      graph.py
      state.py
      nodes.py
      routing.py

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

  rag/
    __init__.py
    retriever.py
    ranker.py
    context_builder.py
    sources/

  utils/
    ...
```

---

## 4. 폴더별 책임

### 4.1 `api/cube/`

Cube 연동 경계다.  
이 계층은 LangGraph 내부 구조를 직접 알지 않고, 채팅 처리 유스케이스 진입점만 호출한다.

주요 책임:

- HTTP endpoint 수신
- payload parsing
- wake-up / empty / duplicate 처리
- Redis queue 적재
- worker 루프 실행
- **최종 Cube 응답 전송** (`client.py`의 `send_multimessage`)

LangGraph 도입 후에도 이 계층은 얇게 유지하는 것이 좋다.

즉, `cube/service.py`는 `chat/service.py`를 호출하여 reply를 받고, 그 reply를 `send_multimessage`로 전달한다.
`chat/` 계층은 Cube의 존재를 모르며, 순수하게 reply 문자열만 반환한다.

### 4.2 `api/chat/`

채팅 요청 처리의 애플리케이션 계층이다.  
Cube worker가 호출하는 실제 진입점은 여기로 모은다.

주요 책임:

- `run_chat_workflow(...)` 진입점 제공
- 요청/응답 모델 정의
- history 조회/저장 연결
- workflow 실행 전후 조립
- **reply 문자열을 반환** (Cube 전송은 하지 않음)

여기서 중요한 점은, `api/chat/`는 LangGraph에 종속된 디렉터리가 아니라는 것이다.
즉, 채팅이라는 유스케이스는 유지하되, 내부 구현으로 LangGraph를 사용하는 구조다.
또한, Cube라는 전송 수단을 전혀 알 필요가 없어 테스트와 재사용이 쉬워진다.

### 4.3 `api/workflows/chat/`

일반 대화 workflow의 LangGraph 구현체다.

주요 책임:

- graph 정의
- state 타입 정의
- node 함수 구현
- conditional routing 구현
- tool loop 구현
- fallback / 정책 분리

예상되는 기본 흐름:

1. context 준비
2. command 여부 판정
3. 필요 tool 선택
4. LLM 호출
5. tool call이 있으면 실행 후 재호출
6. 최종 답변 생성

### 4.4 `api/llm/`

LangChain 모델 인스턴스를 생성·관리하는 **모델 레지스트리** 계층이다.

사내 LLM은 모두 OpenAI-compatible endpoint이므로 `langchain-openai`의 `ChatOpenAI`를 사용한다.
기존 `llm/service.py`의 raw `httpx` 호출은 `ChatOpenAI`로 대체되며, `service.py`는 삭제된다.

주요 책임:

- 사용 가능한 모델 목록 관리 (Kimi-K2.5, Qwen3, GPT-OSS 등)
- 모델별 설정 관리 (base_url, api_key, temperature, max_tokens 등)
- task나 조건에 따른 모델 선택 인터페이스 제공
- `ChatOpenAI` 인스턴스 생성 및 반환

workflow의 각 node는 `llm/registry.py`에서 필요한 모델을 가져다 쓴다.

### 4.5 `api/mcp/`

MCP tool calling을 위한 인프라 계층이다.

초기에는 몇 개의 tool만 붙더라도, 나중에 MCP 서버가 많아지면 아래 기능이 반드시 필요해진다.

- 서버 레지스트리
- 서버별 tool 목록 조회
- tool 목록 캐시
- MCP schema -> OpenAI/LangGraph tool schema 변환
- tool name 기준 서버 라우팅
- timeout / exception 정규화
- 일부 서버 장애 시 graceful degradation

그래서 `mcp`는 workflow 안의 helper가 아니라 독립 패키지로 두는 것이 맞다.

### 4.6 `api/rag/`

RAG 기능 자체를 담당하는 계층이다.

예:

- retriever
- reranker
- context builder
- 문서 source adapter

초기에는 `chat` workflow의 한 node에서 이 계층을 호출하면 충분하다.

### 4.7 `api/workflows/rag/`

RAG가 단순 검색이 아니라 별도 graph가 되어야 할 때만 사용한다.

예:

- query rewrite
- retrieval
- rerank
- context compression
- 검색 실패 fallback

이 수준으로 복잡해지면 `chat` workflow 안의 단일 node로 두기보다 reusable subgraph로 분리하는 편이 낫다.

### 4.8 `api/workflows/agent/`

Agent가 독립적인 planning/execution loop를 가지게 될 때 사용하는 workflow 계층이다.

예:

- 계획 수립
- tool 실행
- 결과 평가
- re-plan
- 종료 조건 판정

처음부터 agent를 여기로 빼는 것은 과하고, 실제로 다단계 loop가 필요해지는 시점에 생성하는 것이 적절하다.

---

## 5. 왜 `chat`과 `workflows/chat`을 분리하는가

이 구분은 중요하다.

### `api/chat/`

- 채팅 유스케이스 계층
- worker나 상위 계층이 호출하는 진입점
- 요청/응답 조립
- history 저장 연결
- command 처리

### `api/workflows/chat/`

- LangGraph 구현 계층
- state, nodes, routing, tool loop

즉:

- `chat`: use case
- `workflows/chat`: engine-specific implementation

이렇게 나누면:

- 테스트 경계를 나누기 쉽고
- LangGraph 의존 범위를 좁힐 수 있고
- 나중에 다른 orchestration 방식으로 바꿔도 외부 진입점은 유지된다

---

## 6. 왜 `workflows/chat` 아래에 `chat` 서브폴더가 필요한가

지금은 `chat` workflow 하나만 있어도, 이후 `rag`, `agent`가 별도 graph가 될 가능성이 높다.  
그래서 처음부터 `api/workflows/`를 상위 네임스페이스로 두고, 그 아래에 workflow 종류별 디렉터리를 두는 편이 안전하다.

즉:

- `api/workflows/chat/`
- `api/workflows/rag/`
- `api/workflows/agent/`

이 구조는 "중간에 호출된다"는 이유로 나누는 것이 아니라,  
"재사용 가능한 LangGraph 단위인가"를 기준으로 나누는 것이다.

정리하면:

- helper / infra 계층이면 `api/rag/`, `api/mcp/`
- reusable graph / subgraph 계층이면 `api/workflows/rag/`, `api/workflows/agent/`

---

## 7. 필요 의존성

LangGraph 도입에 따라 아래 패키지가 추가로 필요하다.

```text
langgraph
langchain-core
langchain-openai
```

기존 `httpx` 기반 직접 호출은 `ChatOpenAI`로 대체되므로, LLM 호출 목적의 `httpx` 사용은 제거된다.
(단, `httpx` 자체는 다른 용도로 사용 중이면 유지)

---

## 8. 마이그레이션 경로

현재 `cube/service.py`의 `process_incoming_message`가 담당하는 책임을 아래와 같이 분리한다.

### 현재 흐름 (`cube/service.py:process_incoming_message`)

```
1. wake-up 판정
2. history 조회 + user message 저장
3. generate_reply (httpx → LLM)
4. assistant message 저장
5. send_multimessage (Cube 응답)
```

### 변경 후 흐름

```
cube/service.py
  ├─ wake-up / empty / duplicate 판정 (유지)
  ├─ chat/service.py::run_chat_workflow() 호출
  │    ├─ history 조회
  │    ├─ workflows/chat/graph 실행
  │    │    ├─ llm/registry에서 모델 선택
  │    │    ├─ mcp tool calling (필요 시)
  │    │    └─ 최종 reply 생성
  │    ├─ history 저장
  │    └─ reply 반환
  └─ send_multimessage (Cube 응답 전송)
```

핵심: `cube/service.py`는 reply를 받아 전송하는 역할만 하고, 대화 로직은 `chat/`과 `workflows/`로 이동한다.

---

## 9. 초기 구현 권장 범위

처음부터 모든 폴더를 다 구현할 필요는 없다.
초기 범위는 아래 정도가 적절하다.

### 9.1 먼저 만드는 것

- `api/chat/`
- `api/workflows/chat/`
- `api/mcp/`
- `api/rag/`

### 9.2 나중에 만드는 것

- `api/workflows/rag/`
- `api/workflows/agent/`

즉, 처음에는 `chat` workflow 하나로 시작하고:

- RAG는 service/node 수준으로 호출
- MCP는 독립 인프라 계층으로 준비
- Agent는 실제 loop가 필요해질 때 workflow로 분리

이 순서가 가장 안전하다.

---

## 10. 예상 인터페이스

초기 구조 기준으로 중요한 인터페이스는 아래와 같다.

### 10.1 `api/chat/service.py`

```python
def run_chat_workflow(incoming, attempt: int = 0):
    ...
```

이 함수가 worker가 호출하는 채팅 유스케이스 진입점이 된다.

### 10.2 `api/workflows/chat/state.py`

예상 state 필드:

- user_id
- channel_id
- user_message
- history
- requested_model
- resolved_model
- selected_tools
- tool_results
- final_reply
- error

### 10.3 `api/llm/registry.py`

핵심 역할:

- 사내 모델 목록 정의 및 관리
- task/조건 기반 모델 선택
- `ChatOpenAI` 인스턴스 생성·반환

예상 인터페이스:

```python
def get_model(task: str | None = None) -> ChatOpenAI:
    """task에 맞는 모델 인스턴스를 반환한다."""
    ...
```

### 10.4 `api/mcp/`

핵심 역할:

- MCP 서버 설정 로딩
- tool 목록 캐시
- tool schema 변환
- tool 실행 라우팅

### 10.5 `api/cube/models.py`

`CubeIncomingMessage`에는 최소한 아래 확장이 필요할 수 있다.

- `requested_model: str | None = None`

이 값은 queue를 통과해도 보존되어야 한다.

---

## 11. 테스트 계획

초기 구조가 들어가면 아래 테스트가 필요하다.

### 11.1 `tests/test_cube_service.py`

- Cube service가 `chat.service`로 위임하는지 검증
- empty / wake-up / duplicate 처리 유지 확인

### 11.2 `tests/test_chat_service.py`

- 채팅 유스케이스 진입점 테스트
- history 연결과 응답 후처리 검증

### 11.3 `tests/test_chat_graph.py`

- 일반 응답 경로
- conditional routing 경로
- tool loop 경로 검증

### 11.4 `tests/test_llm_registry.py`

- 모델 목록 로딩
- task 기반 모델 선택
- 미등록 모델 요청 시 fallback 동작

### 11.5 `tests/test_mcp_registry.py`

- MCP 서버 설정 로딩
- enabled / disabled 처리
- 서버 증가 시 동작 안정성 검증

### 11.6 `tests/test_mcp_executor.py`

- tool name 기준 서버 라우팅
- timeout 처리
- 일부 MCP 서버 장애 시 graceful degradation

### 11.7 `tests/test_rag_retriever.py`

- retrieval 및 context 조합 검증

---

## 12. 최종 권장안

최종적으로는 아래처럼 이해하면 된다.

- `api/chat/`: 채팅 유스케이스
- `api/workflows/chat/`: 현재 주력 LangGraph
- `api/mcp/`: 대규모 MCP tool calling 인프라
- `api/rag/`: retrieval 기능 계층
- `api/workflows/rag/`: 나중에 RAG가 subgraph가 될 때 추가
- `api/workflows/agent/`: 나중에 agent가 독립 loop가 될 때 추가

즉, 지금 당장 모든 workflow를 만들기보다:

1. `chat` workflow부터 시작하고
2. MCP는 처음부터 확장형으로 분리하고
3. RAG와 Agent는 실제 복잡도가 생기면 subgraph로 승격한다

이 방식이 가장 현실적이고 유지보수하기 쉽다.
