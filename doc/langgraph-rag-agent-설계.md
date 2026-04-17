# LangGraph RAG Agent 설계

## 1. 목표

현재 단순 LLM 호출 구조(`llm/service.py`)를 LangGraph 기반 에이전트로 전환한다.

- OpenSearch를 이용한 RAG (문서 검색 → 컨텍스트 주입)
- 도구 호출: SQL 쿼리 실행, 차트 생성/이미지 전송 등
- 기존 Cube 연동 흐름(`cube/service.py` → `cube/worker.py`)과의 호환 유지

---

## 2. 현재 구조 (AS-IS)

```text
cube/service.py::process_incoming_message()
  ├─ conversation_service.get_history()
  ├─ llm/service.py::generate_reply()   ← 단순 OpenAI 호환 HTTP 호출
  ├─ conversation_service.append_message()
  └─ cube/client.py::send_multimessage()
```

`generate_reply()`는 history + user_message를 받아 `/chat/completions`를 호출하고 문자열을 반환한다.
도구 호출, 검색, 조건 분기 없이 1회 요청-응답으로 끝난다.

---

## 3. 목표 구조 (TO-BE)

```text
cube/service.py::process_incoming_message()
  ├─ conversation_service.get_history()
  ├─ api/agent/graph.py::run_agent()     ← LangGraph 에이전트
  │     ├─ [retrieve] OpenSearch RAG 검색
  │     ├─ [agent]    LLM 판단 + 도구 선택
  │     ├─ [tools]    도구 실행 (SQL, 차트 등)
  │     └─ [respond]  최종 응답 생성
  ├─ conversation_service.append_message()
  └─ cube/client.py::send_multimessage()  (이미지 포함 시 send_richnotification)
```

### 에이전트 그래프 흐름

```text
         ┌──────────┐
         │ retrieve │  OpenSearch에서 관련 문서 검색
         └────┬─────┘
              ▼
         ┌──────────┐
    ┌───▶│  agent   │  LLM이 도구 호출 여부 판단
    │    └────┬─────┘
    │         │
    │    도구 호출 있음?
    │    ├─ Yes ──▶ ┌──────────┐
    │    │          │  tools   │  도구 실행 (SQL, 차트 등)
    │    │          └────┬─────┘
    │    │               │
    │    └───────────────┘  (결과를 agent에 재전달)
    │
    │    ├─ No ───▶ ┌──────────┐
    │               │ respond  │  최종 텍스트 응답 반환
    │               └──────────┘
    └── (루프: 도구 결과를 보고 추가 도구 호출 가능)
```

---

## 4. 패키지 구조

```text
api/
├── agent/                    ← 신규 패키지
│   ├── __init__.py           ← run_agent() 공개 인터페이스
│   ├── graph.py              ← LangGraph StateGraph 정의
│   ├── state.py              ← AgentState TypedDict 정의
│   ├── nodes.py              ← 그래프 노드 함수들 (retrieve, agent, tools, respond)
│   ├── retriever.py          ← OpenSearch 벡터 검색 래퍼
│   └── tools/                ← 도구 모음
│       ├── __init__.py       ← 도구 목록 export
│       ├── sql_query.py      ← SQL 실행 도구
│       └── chart.py          ← 차트 생성 도구
├── llm/
│   └── service.py            ← 유지 (LangGraph 내부에서 ChatOpenAI로 대체, 기존 코드는 폴백/레거시용)
└── ...
```

---

## 5. 핵심 모듈 설계

### 5.1 `agent/state.py` — 에이전트 상태 정의

```python
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # 대화 메시지 (LangGraph 자동 누적)
    context: str                                           # RAG 검색 결과 컨텍스트
    final_response: str                                    # 최종 응답 텍스트
```

### 5.2 `agent/retriever.py` — OpenSearch 검색

```python
from opensearchpy import OpenSearch

def retrieve_documents(query: str) -> list[dict]:
    """OpenSearch에서 query와 관련된 문서를 검색하여 반환한다."""
    # - 벡터 검색 (knn) 또는 BM25 키워드 검색
    # - 임베딩 모델은 config에서 지정
    # - top_k, index_name 등도 config 기반
    ...
```

**설정 항목** (`config.py`에 추가):
- `OPENSEARCH_URL` — OpenSearch 클러스터 주소
- `OPENSEARCH_INDEX` — 검색 대상 인덱스명
- `OPENSEARCH_TOP_K` — 검색 결과 수 (기본: 5)
- `EMBEDDING_MODEL` — 임베딩 모델 (벡터 검색 사용 시)

### 5.3 `agent/nodes.py` — 그래프 노드 함수

```python
def retrieve_node(state: AgentState) -> dict:
    """사용자 메시지로 OpenSearch 검색 → context 생성"""
    query = state["messages"][-1].content
    docs = retrieve_documents(query)
    context = "\n\n".join(doc["text"] for doc in docs)
    return {"context": context}


def agent_node(state: AgentState) -> dict:
    """LLM에 context + messages 전달, 도구 호출 여부 판단"""
    # system prompt에 context 주입
    # bind_tools()로 도구 바인딩
    response = llm.invoke(...)
    return {"messages": [response]}


def tools_node(state: AgentState) -> dict:
    """LLM이 요청한 도구를 실행하고 결과를 메시지로 반환"""
    # ToolNode 또는 수동 실행
    ...


def respond_node(state: AgentState) -> dict:
    """최종 응답 텍스트 추출"""
    last_message = state["messages"][-1]
    return {"final_response": last_message.content}
```

### 5.4 `agent/graph.py` — StateGraph 구성

```python
from langgraph.graph import StateGraph, END

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "agent")
    graph.add_conditional_edges(
        "agent",
        should_use_tools,       # tool_calls 존재 여부 판단
        {"tools": "tools", "respond": "respond"},
    )
    graph.add_edge("tools", "agent")  # 도구 결과 → 다시 LLM 판단
    graph.add_edge("respond", END)

    return graph.compile()
```

### 5.5 `agent/__init__.py` — 공개 인터페이스

```python
def run_agent(*, history: list[dict], user_message: str) -> str:
    """기존 generate_reply()와 동일한 시그니처를 유지한다.

    cube/service.py에서 generate_reply() 대신 이 함수를 호출하면 된다.
    """
    graph = build_graph()
    messages = _convert_history(history) + [HumanMessage(content=user_message)]
    result = graph.invoke({"messages": messages, "context": "", "final_response": ""})
    return result["final_response"]
```

---

## 6. 도구 설계

### 6.1 `tools/sql_query.py` — SQL 실행 도구

```python
from langchain_core.tools import tool

@tool
def query_database(sql: str) -> str:
    """회사 내부 데이터베이스에서 SQL 쿼리를 실행한다.

    Args:
        sql: 실행할 SELECT 쿼리 (읽기 전용)
    """
    # - 읽기 전용 연결 사용 (SELECT만 허용)
    # - 결과 행 수 제한
    # - 타임아웃 설정
    ...
```

**설정 항목**:
- `DB_READ_URL` — 읽기 전용 DB 연결 문자열
- `DB_QUERY_TIMEOUT_SECONDS` — 쿼리 타임아웃 (기본: 30)
- `DB_MAX_ROWS` — 최대 반환 행 수 (기본: 100)

**보안 고려사항**:
- SELECT 문만 허용, DDL/DML 차단
- 허용 테이블/스키마 화이트리스트 적용
- 쿼리 실행 로그 기록

### 6.2 `tools/chart.py` — 차트 생성 도구

```python
@tool
def create_chart(chart_type: str, title: str, data: str) -> str:
    """데이터를 기반으로 차트를 생성하고 이미지 URL을 반환한다.

    Args:
        chart_type: 차트 종류 (bar, line, pie 등)
        title: 차트 제목
        data: JSON 형식의 차트 데이터
    """
    # 1. matplotlib/plotly로 차트 생성
    # 2. 이미지를 바이트로 렌더링
    # 3. cdn_service.save_file_bytes()로 CDN에 업로드
    # 4. CDN URL 반환
    ...
```

**기존 코드 재활용**:
- `cdn/cdn_service.py::save_file_bytes()`로 이미지 저장
- CDN URL을 응답에 포함하면 Cube `richnotification`으로 이미지 전달 가능

---

## 7. `cube/service.py` 변경

변경은 최소한으로 한다. `generate_reply()` 호출을 `run_agent()`로 교체하는 것이 핵심이다.

```python
# Before
from api.llm import generate_reply
llm_reply = generate_reply(history=history, user_message=incoming.message)

# After
from api.agent import run_agent
llm_reply = run_agent(history=history, user_message=incoming.message)
```

에이전트 응답에 이미지 URL이 포함된 경우, `send_richnotification()`을 사용하도록 분기 로직 추가가 필요하다.

---

## 8. 설정 추가 (`config.py`)

```python
# OpenSearch (RAG)
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "")
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "")
OPENSEARCH_TOP_K = int(os.environ.get("OPENSEARCH_TOP_K", 5))
OPENSEARCH_USERNAME = os.environ.get("OPENSEARCH_USERNAME", "")
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD", "")

# Embedding (벡터 검색용)
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "")
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", "")

# Database (SQL 도구)
DB_READ_URL = os.environ.get("DB_READ_URL", "")
DB_QUERY_TIMEOUT_SECONDS = int(os.environ.get("DB_QUERY_TIMEOUT_SECONDS", 30))
DB_MAX_ROWS = int(os.environ.get("DB_MAX_ROWS", 100))
```

---

## 9. 의존성 추가 (`requirements.txt`)

```
langgraph
langchain-core
langchain-openai
opensearch-py
matplotlib
```

- `langchain-openai` — 기존 OpenAI 호환 엔드포인트를 `ChatOpenAI`로 연결
- `opensearch-py` — OpenSearch 직접 클라이언트 (LangChain의 OpenSearch wrapper 대신 직접 사용하여 의존성 최소화)
- `matplotlib` — 차트 생성용

---

## 10. 구현 순서

### Phase 1: 기본 에이전트 프레임 구축
1. `api/agent/` 패키지 생성 (`state.py`, `graph.py`, `nodes.py`, `__init__.py`)
2. 도구 없이 단순 LLM 호출만 하는 그래프 구성
3. `run_agent()`가 기존 `generate_reply()`와 동일한 결과를 반환하는지 테스트
4. `cube/service.py`에서 호출 교체

### Phase 2: OpenSearch RAG 연결
5. `config.py`에 OpenSearch 설정 추가
6. `agent/retriever.py` 구현
7. `retrieve` 노드에서 검색 결과를 context로 주입
8. RAG 동작 테스트

### Phase 3: 도구 추가
9. `tools/sql_query.py` 구현 + 보안 제약 적용
10. `tools/chart.py` 구현 + CDN 연동
11. 도구 바인딩 및 조건 분기 테스트

### Phase 4: Cube 응답 확장
12. 이미지 URL 포함 시 `richnotification` 분기 로직 구현
13. 통합 테스트

---

## 11. 테스트 전략

- **단위 테스트**: 각 노드 함수를 독립적으로 테스트 (OpenSearch/DB는 mock)
- **그래프 테스트**: 도구 호출 경로 분기가 올바르게 동작하는지 확인
- **통합 테스트**: 집에서는 mock 기반, 사무실에서는 실제 OpenSearch/DB 연결 테스트
- 기존 `tests/test_llm_service.py` 패턴을 따라 `tests/test_agent.py` 작성

---

## 12. 주의 사항

- **기존 `llm/service.py`는 삭제하지 않는다** — 에이전트 전환 후에도 폴백용 또는 단순 호출용으로 유지
- **환경 변수 미설정 시 graceful 처리** — OpenSearch/DB URL이 없으면 해당 기능을 스킵하고 기본 LLM 응답만 반환
- **SQL 도구 보안** — SELECT만 허용, 화이트리스트, 타임아웃 필수
- **LLM 타임아웃** — 도구 호출 루프가 길어질 수 있으므로 전체 에이전트 실행 타임아웃 설정 필요
- **대화 이력 변환** — 기존 `{"role": "user", "content": "..."}` 딕셔너리를 LangChain `BaseMessage`로 변환하는 유틸 필요
