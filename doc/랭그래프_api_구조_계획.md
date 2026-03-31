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

### 2.4 Cube와 queue 계층은 얇게 유지하고, 응답 포맷 라우팅을 담당한다

현재 `cube` 계층은 HTTP ingress, payload parsing, queue 적재, worker 실행에 강점이 있다.
LangGraph 도입 후에도 `api/cube/`는 이 책임만 유지하고, 실제 대화 판단은 `chat`과 `workflows`로 옮긴다.

단, **Cube 응답 전송은 `cube/service.py`가 담당한다.**
`chat/service.py`는 `ChatResult` 구조체를 반환하고, `cube/service.py`가 이를 받아서 적절한 포맷으로 전달한다.
이렇게 하면 `chat/` 계층은 Cube를 전혀 알 필요가 없다.

#### Cube 응답 포맷: multimessage vs richnotification

Cube 플랫폼은 두 가지 응답 방식을 제공한다.

| | multimessage | richnotification |
|---|---|---|
| 형태 | 순수 텍스트 | 이미지 기반 렌더링 |
| 복사 가능 여부 | 사용자가 텍스트를 복사할 수 있음 | 이미지이므로 복사 불가 |
| 상호작용 | 없음 | 테이블, 버튼, 메뉴 등 지원 |
| 포맷 | plain text만 가능 | 자체 포맷 (구조화된 JSON) |
| 현재 상태 | **사용 중** | 미구현, 이후 추가 예정 |

**현재 전략:**

- 초기에는 `send_multimessage`만 사용한다. 사용자가 LLM 답변을 복사·붙여넣기할 수 있어야 하므로 텍스트 기반이 우선이다.
- 이후 richnotification을 구현하면, LLM이 생성하는 콘텐츠 유형에 따라 두 포맷을 조합한다.
  - 텍스트 답변 → multimessage (복사 가능)
  - 테이블, 선택지, 구조화된 데이터 → richnotification (인터랙티브)
  - 복합 콘텐츠 → 두 포맷을 함께 전송

**설계 함의:**

- `chat/` 계층은 Cube 포맷을 모른다. 구조화된 `ChatResult`를 반환할 뿐이다.
- `cube/service.py`가 `ChatResult`의 내용을 보고 multimessage / richnotification / 혼합 중 어떤 방식으로 전달할지 결정한다.
- 이를 위해 `cube/` 내에 응답 포맷 변환 로직이 필요하며, `cube/payload.py`가 이를 담당한다.

### 2.5 chat/service.py는 ChatResult 구조체를 반환한다

`chat/service.py`의 `run_chat_workflow()`는 단순 reply 문자열이 아니라 `ChatResult` 구조체를 반환한다.

```python
@dataclass(frozen=True, slots=True)
class ChatResult:
    reply: str              # LLM이 생성한 텍스트 답변
    model_used: str         # 실제 사용된 모델 이름
    tool_calls: list[str]   # 호출된 tool 이름 목록
    thread_id: str          # checkpointer thread_id
```

이유:

- `cube/service.py`가 응답 포맷(multimessage / richnotification)을 선택하려면 reply 외 메타데이터가 필요하다.
- `archive/service.py`가 `model_used`, `tool_calls` 등을 인덱싱하려면 이 정보가 `chat/` 밖으로 나와야 한다.
- reply만 반환하면 상위 계층이 workflow 내부를 직접 참조해야 하므로 계층 분리가 무너진다.

`ChatResult`는 `chat/models.py`에 정의한다.

### 2.6 LLM 계층은 LangChain 모델 제공자로 사용한다

사내 LLM은 모두 OpenAI-compatible endpoint이므로 `langchain-openai`의 `ChatOpenAI`를 사용한다.
`api/llm/`은 모델 인스턴스를 생성해 반환하는 **모델 레지스트리** 역할을 한다.

- 모델별 설정(base_url, api_key, temperature 등)을 관리
- task나 조건에 따라 적절한 모델을 선택할 수 있는 인터페이스 제공
- workflow의 각 node가 필요한 모델을 registry에서 가져다 쓰는 구조

기존 `llm/service.py`의 raw `httpx` 호출은 `ChatOpenAI`로 대체된다.

### 2.7 대화 히스토리는 checkpointer가 관리하고, 완료된 대화는 OpenSearch로 아카이빙한다

LangGraph checkpointer(`MongoDBSaver`)가 대화 히스토리의 저장/복원을 자동으로 처리한다.
기존 `conversation_service.py`의 수동 `get_history` / `append_message` 패턴은 제거된다.

다만 checkpointer는 메시지를 무한히 누적하므로, 완료된 대화에서 중요 정보를 추출하여 **OpenSearch에 아카이빙**한 뒤 오래된 메시지를 트리밍하는 전략이 필요하다.

흐름:

1. 대화 처리 완료 후, 비동기로 아카이빙 수행
2. 대화에서 키워드, 주제, 사용자 만족도 신호 추출
3. OpenSearch에 인덱싱 (검색, 분석, 품질 개선용)
4. 주기적으로 오래된 checkpointer 히스토리를 트리밍

사용자 불만족 대화는 아카이브에 플래그를 달아 나중에 분석·개선할 수 있다.

#### thread_id 전략

checkpointer의 `thread_id`는 **`user_id`를 단독으로 사용**한다.

- 현재 시스템이 이미 `user_id` 단위로 히스토리를 관리하고 있어 동작이 동일하다.
- `user_id:channel_id`로 분리하면 채널 간 대화 맥락이 끊어져 사용자 경험이 나빠진다.
- `!model` 명령의 모델 선호는 대화 히스토리와 별개이므로, `user_id:channel_id` 키로 별도 저장소(Redis 또는 MongoDB)에 관리한다.
- LangGraph의 `thread_id`는 단순 문자열이므로, 나중에 키 형식을 변경해도 구조 변경 없이 대응할 수 있다.

#### 개발/운영 환경 분리

- **개발**: `MemorySaver`를 사용한다 (env var로 선택).
- **운영**: `MongoDBSaver`를 사용한다. MongoDB 장애 시 in-memory로 자동 전환하지 않는다.

기존 `conversation_service.py`의 자동 fallback은 개발 편의를 위한 것이었지만, checkpointer 환경에서는 명시적 환경 분리가 더 안전하다. 운영 중 MongoDB가 불가하면 worker가 실패하고 queue가 재시도한다 — 이것이 올바른 동작이다.

#### 운영 대시보드용 read model

기존 `conversation_service.py`의 `get_recent()` (최근 대화 조회)는 Flask `/` 화면에서 사용 중이다.
checkpointer는 이 용도에 적합하지 않으므로, 별도 read model로 분리한다.

- 단기: `cube/service.py`에서 reply 전송 시 간단한 MongoDB collection에 append (별도 collection, append-only)
- 중기: `archive/` 계층이 OpenSearch에 인덱싱하면 대시보드도 OpenSearch에서 조회

---

## 3. 권장 `api/` 폴더 구조

```text
api/
  __init__.py
  blueprint_loader.py
  config.py
  conversation_service.py       # → checkpointer로 대체 예정, 이후 제거

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
    commands.py

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
이 계층은 LangGraph 내부 구조를 직접 알지 않고, 채팅 처리 유스케이스 진입점만 호출한다.

주요 책임:

- HTTP endpoint 수신
- payload parsing
- wake-up / empty / duplicate 처리
- Redis queue 적재
- worker 루프 실행
- **최종 Cube 응답 전송 및 포맷 라우팅**
  - `ChatResult`의 내용을 보고 multimessage / richnotification / 혼합 중 선택
  - 초기에는 `send_multimessage`(plain text)만 사용
  - richnotification 구현 후에는 `payload.py`가 콘텐츠 유형에 따라 적절한 포맷으로 변환

LangGraph 도입 후에도 이 계층은 얇게 유지하는 것이 좋다.

즉, `cube/service.py`는 `chat/service.py`를 호출하여 `ChatResult`를 받고, 그 내용을 적절한 Cube 포맷으로 변환하여 전달한다.
`chat/` 계층은 Cube의 존재를 모르며, 순수하게 `ChatResult` 구조체만 반환한다.

### 4.2 `api/chat/`

채팅 요청 처리의 애플리케이션 계층이다.  
Cube worker가 호출하는 실제 진입점은 여기로 모은다.

주요 책임:

- `run_chat_workflow(...)` 진입점 제공
- 요청/응답 모델 정의 (`ChatResult` 구조체 포함)
- `!` 접두사 command 판정 및 처리 (`commands.py`)
- history 조회/저장 연결
- workflow 실행 전후 조립
- **`ChatResult`를 반환** (reply + model_used + tool_calls + thread_id, Cube 전송은 하지 않음)

여기서 중요한 점은, `api/chat/`는 LangGraph에 종속된 디렉터리가 아니라는 것이다.
즉, 채팅이라는 유스케이스는 유지하되, 내부 구현으로 LangGraph를 사용하는 구조다.
또한, Cube라는 전송 수단을 전혀 알 필요가 없어 테스트와 재사용이 쉬워진다.

#### `commands.py` — 사용자 명령어 처리

Cube 플랫폼이 `/` 접두사를 자체 명령어로 사용하므로, 봇 명령어는 `!` 접두사를 사용한다.

command가 감지되면 workflow를 타지 않고 `commands.py`에서 직접 처리하여 결과를 반환한다.

예정된 명령어:

| 명령어 | 설명 |
|---|---|
| `!model [이름]` | 사용할 LLM 모델 변경 (인자 없으면 현재 모델 표시 또는 목록) |
| `!remove` | 해당 사용자의 대화 히스토리 삭제 |

이후 필요에 따라 명령어를 추가한다.

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
2. 필요 tool 선택
3. LLM 호출
4. tool call이 있으면 실행 후 재호출
5. 최종 답변 생성

참고: `!` command 판정은 `chat/service.py`에서 workflow 진입 전에 처리한다.
command이면 workflow를 타지 않고 직접 결과를 반환한다.

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

### 4.7 `api/archive/`

완료된 대화에서 중요 정보를 추출하고 OpenSearch에 아카이빙하는 계층이다.

주요 책임:

- 대화 메시지에서 키워드, 주제, 의도 추출 (`extractor.py`)
- 사용자 만족도 신호 감지 (불만족 표현, 재질문 패턴 등)
- 추출된 데이터를 OpenSearch에 인덱싱 (`opensearch_client.py`)
- 아카이빙 완료 후 checkpointer의 오래된 메시지 트리밍

#### 아카이빙 타이밍

대화 처리가 완료된 후 **비동기**로 수행한다.
사용자 응답 속도에 영향을 주지 않는 것이 원칙이다.

```
cube/service.py
  ├─ chat/service.py 호출 → ChatResult 수신
  ├─ ChatResult 기반 응답 포맷 결정 → send_multimessage / richnotification
  ├─ reply_sent 플래그 기록 (Redis, message_id 키, 재시도 시 중복 전송 방지)
  └─ archive/service.py 호출 (비동기, 실패해도 대화 흐름에 영향 없음)
```

#### 멱등성(idempotency) 전략

queue 재시도와 비동기 아카이빙이 결합되면, 동일 메시지가 두 번 처리될 수 있다.
별도 outbox 패턴은 현재 규모에서 과도하므로, 아래 경량 전략을 사용한다.

- **Cube 응답 중복 방지**: `cube:reply_sent:{message_id}` 키를 Redis에 기록 (짧은 TTL). 재시도 경로에서 이 플래그를 확인하고, 이미 전송된 경우 `send_multimessage`를 건너뛴다.
- **아카이빙 멱등성**: OpenSearch 문서 ID로 `message_id`를 사용한다. 같은 메시지가 두 번 아카이빙되어도 upsert이므로 부작용이 없다.
- **checkpointer 보호**: LangGraph graph가 이미 완료된 상태면 checkpointer가 동일 입력에 대해 캐시된 결과를 반환하므로, LLM이 중복 호출되지 않는다.

#### OpenSearch 인덱스 구조 (예시)

```json
{
  "user_id": "user-123",
  "channel_id": "ch-456",
  "thread_id": "user-123",
  "timestamp": "2026-03-31T10:00:00Z",
  "user_message": "...",
  "assistant_reply": "...",
  "keywords": ["키워드1", "키워드2"],
  "topic": "일정 관리",
  "satisfaction": "neutral",
  "model_used": "kimi-k2.5",
  "tool_calls": ["tool_name_1"],
  "flagged": false
}
```

#### 불만족 대화 처리

사용자가 답변에 만족하지 않는 경우 (`satisfaction: "unsatisfied"`):

- 아카이브에 `flagged: true`로 표시
- OpenSearch에서 `flagged` 대화만 필터링하여 분석 가능
- 나중에 프롬프트 개선, 모델 변경, RAG 소스 보강 등에 활용

#### checkpointer 히스토리 트리밍

아카이빙이 완료된 오래된 대화는 checkpointer에서 트리밍할 수 있다.
이 작업은 `scheduled_tasks/`에서 주기적으로 수행한다.

- 아카이빙 완료 확인 후 N일 이상 된 메시지 삭제
- 최근 M개 메시지는 항상 유지 (즉시 대화 재개를 위해)

### 4.8 `api/workflows/rag/`

RAG가 단순 검색이 아니라 별도 graph가 되어야 할 때만 사용한다.

예:

- query rewrite
- retrieval
- rerank
- context compression
- 검색 실패 fallback

이 수준으로 복잡해지면 `chat` workflow 안의 단일 node로 두기보다 reusable subgraph로 분리하는 편이 낫다.

### 4.9 `api/workflows/agent/`

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
- `!` command 판정 및 처리

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
langgraph-checkpoint-mongodb
opensearch-py
```

- 기존 `httpx` 기반 직접 호출은 `ChatOpenAI`로 대체되므로, LLM 호출 목적의 `httpx` 사용은 제거된다.
  (단, `httpx` 자체는 다른 용도로 사용 중이면 유지)
- `langgraph-checkpoint-mongodb`: 대화 히스토리를 MongoDB에 자동 저장/복원
- `opensearch-py`: 완료된 대화의 아카이빙 및 검색

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
  ├─ chat/service.py::run_chat_workflow() 호출 → ChatResult 수신
  │    ├─ ! command 판정 → command이면 직접 처리 후 ChatResult 반환
  │    ├─ workflows/chat/graph 실행 (checkpointer가 history 자동 관리)
  │    │    ├─ llm/registry에서 모델 선택
  │    │    ├─ mcp tool calling (필요 시)
  │    │    └─ 최종 ChatResult 생성 (reply + model_used + tool_calls + thread_id)
  │    └─ ChatResult 반환
  ├─ 응답 포맷 결정 (ChatResult 기반)
  │    ├─ 텍스트 답변 → send_multimessage (plain text, 복사 가능)
  │    ├─ 구조화 콘텐츠 → send_richnotification (이후 구현)
  │    └─ 복합 → 두 포맷 조합 (이후 구현)
  ├─ reply_sent 플래그 기록 (Redis, 재시도 시 중복 방지)
  └─ archive/service.py 호출 (비동기, message_id 기반 멱등)
       ├─ 키워드·주제·만족도 추출
       └─ OpenSearch 인덱싱
```

핵심: `cube/service.py`는 `ChatResult`를 받아 적절한 Cube 포맷으로 변환·전송하는 역할만 하고, 대화 로직은 `chat/`과 `workflows/`로 이동한다.

---

## 9. 초기 구현 권장 범위

처음부터 모든 폴더를 다 구현할 필요는 없다.
초기 범위는 아래 정도가 적절하다.

### 9.1 먼저 만드는 것

- `api/chat/`
- `api/workflows/chat/`
- `api/llm/` (registry 리팩터링)
- `api/archive/` (OpenSearch 아카이빙)
- `api/mcp/`

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
def run_chat_workflow(incoming: CubeIncomingMessage, attempt: int = 0) -> ChatResult:
    """
    worker가 호출하는 채팅 유스케이스 진입점.
    ChatResult를 반환하며, Cube 전송은 하지 않는다.
    """
    ...
```

`ChatResult`는 `chat/models.py`에 정의한다:

```python
@dataclass(frozen=True, slots=True)
class ChatResult:
    reply: str              # LLM이 생성한 텍스트 답변
    model_used: str         # 실제 사용된 모델 이름
    tool_calls: list[str]   # 호출된 tool 이름 목록
    thread_id: str          # checkpointer thread_id (= user_id)
```

### 10.2 `api/workflows/chat/state.py`

예상 state 필드:

- messages (`Annotated[list[BaseMessage], add_messages]` — checkpointer가 자동 관리)
- user_id
- channel_id
- requested_model
- resolved_model (`ChatResult.model_used`에 반영)
- selected_tools
- tool_results (`ChatResult.tool_calls`에 반영)
- error

`thread_id`는 `user_id`를 단독으로 사용한다 (§2.7 참조).
`RunnableConfig(configurable={"thread_id": user_id})`로 graph를 실행한다.

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

### 10.4 `api/archive/service.py`

핵심 역할:

- 완료된 대화에서 키워드·주제·만족도 추출
- OpenSearch에 인덱싱
- checkpointer 히스토리 트리밍 (scheduled task에서 호출)

예상 인터페이스:

```python
def archive_conversation(thread_id: str, messages: list[BaseMessage], **metadata) -> None:
    """대화를 OpenSearch에 아카이빙한다. 비동기로 호출된다."""
    ...

def trim_old_history(thread_id: str, *, keep_recent: int = 20) -> None:
    """아카이빙 완료된 오래된 메시지를 checkpointer에서 제거한다."""
    ...
```

### 10.5 `api/mcp/`

핵심 역할:

- MCP 서버 설정 로딩
- tool 목록 캐시
- tool schema 변환
- tool 실행 라우팅

### 10.6 `api/cube/models.py`

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

### 11.7 `tests/test_archive_service.py`

- 대화 메시지에서 키워드·만족도 추출 검증
- OpenSearch 인덱싱 호출 검증 (mock)
- 아카이빙 실패 시 대화 흐름에 영향 없음 확인

### 11.8 `tests/test_rag_retriever.py`

- retrieval 및 context 조합 검증

---

## 12. 최종 권장안

최종적으로는 아래처럼 이해하면 된다.

- `api/chat/`: 채팅 유스케이스 (command 처리 포함)
- `api/workflows/chat/`: 현재 주력 LangGraph
- `api/llm/`: LangChain 모델 레지스트리 (task 기반 모델 선택)
- `api/mcp/`: 대규모 MCP tool calling 인프라
- `api/archive/`: 대화 아카이빙 (OpenSearch) + 히스토리 트리밍
- `api/rag/`: retrieval 기능 계층
- `api/workflows/rag/`: 나중에 RAG가 subgraph가 될 때 추가
- `api/workflows/agent/`: 나중에 agent가 독립 loop가 될 때 추가

대화 히스토리 관리:

- **실시간**: LangGraph checkpointer (`MongoDBSaver`)가 자동 저장/복원
- **아카이빙**: 완료된 대화 → `archive/`가 키워드·만족도 추출 → OpenSearch 인덱싱
- **트리밍**: `scheduled_tasks/`에서 주기적으로 오래된 checkpointer 히스토리 정리
- **기존** `conversation_service.py`는 checkpointer로 대체 후 제거

즉, 지금 당장 모든 workflow를 만들기보다:

1. `chat` workflow부터 시작하고
2. MCP는 처음부터 확장형으로 분리하고
3. 아카이빙은 초기부터 구축하여 대화 품질 개선에 활용하고
4. RAG와 Agent는 실제 복잡도가 생기면 subgraph로 승격한다

이 방식이 가장 현실적이고 유지보수하기 쉽다.
