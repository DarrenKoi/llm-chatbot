# RAG + MCP 통합 아키텍처

## 1. 목적

현재 LLM Chatbot은 사용자 메시지를 받아 대화 이력과 함께 LLM에 전달하고, 텍스트 응답을 반환하는 단순 대화 루프만 지원한다. 이 문서는 아래 두 기능을 기존 아키텍처에 통합하는 설계를 정리한다.

- **RAG (Retrieval-Augmented Generation)**: 지식 베이스에서 관련 문맥을 검색해 LLM 응답 품질을 높인다.
- **MCP (Model Context Protocol) 도구 연동**: LLM이 외부 도구를 호출하여 실시간 데이터 조회, 업무 시스템 연동 등을 수행한다.

핵심 원칙:

- 이 저장소(챗봇)는 **MCP 클라이언트** 역할만 한다.
- 각 MCP 도구 서버는 **별도 저장소, 별도 서비스, 별도 URL**로 운영한다.
- RAG는 **내장 모듈**로 구현하여 매 요청마다 자동 실행한다.
- 기존 코드의 핵심 구조(큐 기반 비동기 처리, 환경 변수 설정, 자동 탐색 패턴)를 유지한다.

---

## 2. 전체 아키텍처

```text
사용자
  │
  ▼
Cube 메신저
  │  POST /api/v1/cube/receiver
  ▼
┌──────────────────────────────────────────────────────────────────┐
│ LLM Chatbot 서버 (Flask + uWSGI)                                │
│                                                                  │
│  cube/router.py → cube/service.py → cube/queue.py               │
│       ↓                                                          │
│  cube/worker.py                                                  │
│       │                                                          │
│       ├─ conversation_service.py  (대화 이력 조회)                │
│       │                                                          │
│       ├─ [신규] rag/retriever.py  (지식 베이스 검색)              │
│       │       │                                                  │
│       │       ├─ OpenSearch (kNN 벡터 검색)                      │
│       │       └─ 외부 검색 API (확장용)                           │
│       │                                                          │
│       ├─ [신규] mcp/client.py     (MCP 클라이언트)                │
│       │       │                                                  │
│       │       ├─ MCP 서버 A (SSE)  ── 별도 서비스/별도 레포       │
│       │       ├─ MCP 서버 B (SSE)  ── 별도 서비스/별도 레포       │
│       │       └─ MCP 서버 C (SSE)  ── 별도 서비스/별도 레포       │
│       │                                                          │
│       ├─ llm/service.py           (LLM 호출 + 에이전틱 루프)     │
│       │                                                          │
│       └─ cube/client.py           (Cube 응답 전송)               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 메시지 처리 흐름 (변경 후)

기존 흐름과 비교하여 RAG 검색, 도구 정의 수집, 에이전틱 루프가 추가된다.

```text
1.  Cube → POST /api/v1/cube/receiver
2.  cube/service.py가 입력 검증 후 Redis 큐에 적재
3.  cube/worker.py가 큐에서 메시지를 읽음
4.  conversation_service.get_history()로 대화 이력 조회
5.  사용자 메시지를 대화 이력에 append

── 여기까지 기존과 동일 ──

6.  [신규] rag/retriever.py로 사용자 메시지 기반 관련 문맥 검색
    - 사용자 메시지 임베딩 생성 (이 임베딩을 6.5에서 재사용)
7.  [신규] mcp/tool_selector.py: 도구 필요 여부 판단 + 관련 도구 선택
    - 6단계에서 생성한 임베딩과 도구 description 임베딩의 유사도 비교
    - 유사도 max < threshold → tools=None (도구 불필요, 일반 대화)
    - 유사도 ≥ threshold → 해당 도구만 선택 (도구 필요, 선택된 것만 전달)
    - 상세: §5.10 도구 선택 전략 참조
8.  [변경] llm/service.py가 메시지 배열 구성:
    - system prompt + RAG 문맥 + 대화 이력 + 사용자 메시지
    - tools 파라미터에 MCP 도구 정의 포함
9.  [변경] LLM API 호출 (/chat/completions)
10. [신규] LLM 응답에 tool_calls가 있으면:
    a. 각 tool_call을 해당 MCP 서버로 라우팅
    b. 도구 실행 결과를 메시지 배열에 추가
    c. LLM 재호출 (에이전틱 루프, 최대 반복 제한)
    d. tool_calls가 없을 때까지 반복
11. 최종 텍스트 응답을 대화 이력에 append
12. cube/client.py로 Cube에 답변 전송
```

---

## 4. RAG 아키텍처

### 4.1 설계 결정: 내장 모듈 vs MCP 도구

RAG를 MCP 도구 서버로 구현하는 방안도 고려했으나, **내장 모듈**로 구현하는 것이 적합하다.

| 기준 | 내장 모듈 | MCP 도구 |
|------|-----------|----------|
| 실행 시점 | 매 요청마다 자동 실행 | LLM이 호출을 결정해야 실행 |
| 지연 시간 | 네트워크 홉 없이 직접 호출 | SSE 연결 + JSON-RPC 오버헤드 |
| 결과 위치 | system prompt에 직접 주입 | tool 결과로 메시지 배열에 추가 |
| 제어 가능성 | 항상 실행되므로 예측 가능 | LLM 판단에 의존, 누락 가능 |

RAG는 "LLM이 판단해서 호출하는 도구"가 아니라 "매 요청에 자동으로 맥락을 보강하는 전처리 단계"다. 따라서 내장 모듈이 더 단순하고 안정적이다.

### 4.2 패키지 구조

```text
api/rag/
├── __init__.py          # retrieve_context() 공개
└── retriever.py         # 검색 로직 (OpenSearch / 외부 API)
```

### 4.3 인터페이스

```python
# api/rag/retriever.py

def retrieve_context(query: str, *, top_k: int = 5) -> list[dict[str, str]]:
    """
    사용자 질의와 관련된 문서 청크를 검색한다.

    Returns:
        [{"source": "문서명", "content": "관련 텍스트 청크"}, ...]
    """
```

### 4.4 RAG 문맥 주입 위치

`llm/service.py`의 `_build_messages()` 함수에서 system prompt 바로 다음에 RAG 문맥을 삽입한다.

```text
messages 배열 구성 순서:
1. system prompt (기존)
2. [신규] RAG 문맥 (role: "system")
3. 대화 이력 (기존)
4. 사용자 메시지 (기존)
```

RAG 문맥 포맷 예시:

```text
[참고 자료]
아래는 사용자 질문과 관련된 내부 문서입니다. 답변 시 이 정보를 활용하세요.
답변에 활용할 수 없는 내용은 무시하세요.

---
출처: VPN 설정 가이드
내용: VPN 접속을 위해서는 먼저 GlobalProtect 클라이언트를 설치해야 합니다...

---
출처: 사내 네트워크 정책
내용: 외부 접속 시 보안 VPN을 반드시 사용해야 하며...
```

### 4.5 RAG 백엔드 설계

OpenSearch를 기본 백엔드로 사용하되, 외부 검색 API를 추가로 호출할 수 있도록 확장 가능한 구조로 설계한다.

```text
retrieve_context(query)
  │
  ├─ OpenSearch kNN 검색 (기본)
  │   └─ 벡터 임베딩 → 유사도 검색 → 결과 반환
  │
  └─ 외부 검색 API (선택, 추가 정보 보강)
      └─ HTTP 호출 → 결과 반환
  │
  └─ 두 결과를 병합하여 반환
```

외부 API는 설정이 있을 때만 호출한다. OpenSearch만 사용해도 정상 동작해야 한다.

### 4.6 RAG 관련 환경 변수

```text
RAG_ENABLED=false                        # 전역 활성화 플래그
RAG_OPENSEARCH_URL=                      # OpenSearch 엔드포인트
RAG_OPENSEARCH_INDEX=knowledge_chunks    # 검색 대상 인덱스
RAG_OPENSEARCH_AUTH_USER=                # 인증 사용자
RAG_OPENSEARCH_AUTH_PASSWORD=            # 인증 비밀번호
RAG_SUPPLEMENT_API_URL=                  # 추가 외부 검색 API URL (선택)
RAG_SUPPLEMENT_API_KEY=                  # 추가 외부 검색 API 키 (선택)
RAG_TOP_K=5                              # 검색 결과 최대 건수
RAG_MIN_SCORE=0.5                        # 최소 유사도 점수 (이하 제외)
RAG_MAX_CONTEXT_CHARS=4000               # RAG 문맥 최대 글자 수
```

`RAG_ENABLED=false`이면 RAG 검색을 건너뛰어 기존 동작과 동일하게 유지한다.

---

## 5. MCP 클라이언트 아키텍처

### 5.1 설계 원칙

- 이 저장소는 MCP **클라이언트**만 구현한다.
- 각 MCP 서버는 별도 저장소, 별도 배포, 별도 URL로 운영한다.
- MCP 서버 목록은 환경 변수로 등록한다.
- 도구 정의는 캐싱하여 매 요청마다 전체 서버에 질의하지 않는다.
- 서버 장애 시 해당 서버의 도구만 제외하고 나머지는 정상 동작한다.

### 5.2 패키지 구조

```text
api/mcp/
├── __init__.py          # MCPClient 싱글턴 접근
├── client.py            # MCP 클라이언트 핵심 로직
├── registry.py          # MCP 서버 등록 정보 관리
├── models.py            # MCPServerConfig, MCPTool 등 dataclass
└── errors.py            # MCPClientError 등 예외 정의
```

### 5.3 MCP 서버 레지스트리

서버 목록은 JSON 환경 변수로 관리한다.

```text
MCP_SERVERS_JSON='[
  {
    "name": "jira",
    "url": "https://mcp-jira.internal.example.com",
    "api_key": "env:MCP_JIRA_API_KEY",
    "timeout_seconds": 15,
    "enabled": true,
    "keywords": ["jira", "지라", "이슈", "티켓"]
  },
  {
    "name": "confluence",
    "url": "https://mcp-confluence.internal.example.com",
    "api_key": "env:MCP_CONFLUENCE_API_KEY",
    "timeout_seconds": 15,
    "enabled": true,
    "keywords": ["confluence", "컨플루언스", "위키", "문서"]
  },
  {
    "name": "monitoring",
    "url": "https://mcp-monitoring.internal.example.com",
    "api_key": "",
    "timeout_seconds": 10,
    "enabled": true,
    "keywords": ["모니터링", "장애", "알림", "서버상태"]
  }
]'
```

`api_key` 값이 `env:` 접두사로 시작하면 해당 환경 변수에서 실제 값을 읽는다. JSON에 시크릿을 직접 넣지 않기 위한 패턴이다.

서버 설정 dataclass:

```python
@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    name: str               # 서버 식별 이름
    url: str                # SSE 엔드포인트 기본 URL
    api_key: str = ""       # 인증 키 (빈 문자열이면 미사용)
    timeout_seconds: int = 15
    enabled: bool = True
    keywords: tuple[str, ...] = ()  # 도구 선택 키워드 오버라이드 (§5.10.8)
```

### 5.4 도구 탐색 (Tool Discovery)

MCP 프로토콜에서 클라이언트는 서버의 `tools/list` 메서드를 호출하여 사용 가능한 도구 목록을 받는다.

```text
탐색 흐름:

1. 워커 시작 시:
   - 등록된 모든 enabled MCP 서버에 tools/list 요청
   - 각 서버의 도구 정의를 내부 캐시에 저장
   - 실패한 서버는 로그 기록 후 건너뜀

2. 주기적 갱신 (스케줄러 또는 TTL 기반):
   - 설정 가능한 간격 (기본 5분)으로 캐시 갱신
   - 새 도구가 추가되거나 서버가 복구되면 자동 반영

3. 요청 시점:
   - 캐시에서 도구 정의를 읽어 LLM에 전달
   - 캐시가 비어있으면 동기 탐색 1회 시도
```

도구 캐시 구조:

```python
# 서버별 도구 목록
_tool_cache: dict[str, list[MCPTool]] = {
    "jira": [MCPTool(name="create_issue", ...), MCPTool(name="search_issues", ...)],
    "confluence": [MCPTool(name="search_pages", ...)],
}

# 도구 이름 → 서버 이름 역매핑 (라우팅용)
_tool_server_map: dict[str, str] = {
    "create_issue": "jira",
    "search_issues": "jira",
    "search_pages": "confluence",
}
```

### 5.5 도구 호출 라우팅

LLM이 `tool_calls`를 반환하면, 각 호출을 올바른 MCP 서버로 라우팅한다.

```python
def call_tool(tool_name: str, arguments: dict) -> dict:
    """
    도구 이름으로 담당 MCP 서버를 찾아 tools/call 요청을 보낸다.
    """
    server_name = _tool_server_map.get(tool_name)
    if server_name is None:
        return {"error": f"알 수 없는 도구: {tool_name}"}

    server_config = _get_server_config(server_name)
    return _send_tool_call(server_config, tool_name, arguments)
```

### 5.6 전송 프로토콜

별도 서비스로 운영하는 원격 MCP 서버와의 통신에는 **Streamable HTTP (SSE)** 전송을 사용한다.

```text
클라이언트 → 서버: HTTP POST (JSON-RPC 요청)
서버 → 클라이언트: SSE 스트림 또는 JSON 응답
```

초기 구현에서는 **httpx 기반 경량 클라이언트**로 시작한다. MCP 서버가 표준 JSON-RPC 엔드포인트를 제공하면 httpx POST 호출만으로 충분하다.

```text
방안 1: httpx 경량 클라이언트 (초기 권장)
  - 장점: 기존 httpx 스택 재사용, 동기 호출 가능, 의존성 최소
  - 단점: MCP 프로토콜 변경 시 수동 대응 필요

방안 2: MCP Python SDK (향후 전환)
  - 장점: 프로토콜 준수 보장, 스펙 변경 자동 대응
  - 단점: asyncio 의존, 동기 워커와의 호환 처리 필요
```

MCP 서버 수가 늘어나고 프로토콜 복잡도가 높아지면 SDK로 전환한다.

### 5.7 MCP 도구 정의 → OpenAI tools 변환

MCP 서버에서 받은 도구 정의를 OpenAI `tools` 파라미터 형식으로 변환하여 LLM에 전달한다.

```text
MCP 도구 정의:                          OpenAI tools 형식:
{                                       {
  "name": "create_issue",                 "type": "function",
  "description": "이슈 생성",             "function": {
  "inputSchema": {                          "name": "create_issue",
    "type": "object",                       "description": "이슈 생성",
    "properties": {...},                    "parameters": {
    "required": [...]                         "type": "object",
  }                                           "properties": {...},
}                                             "required": [...]
                                            }
                                          }
                                        }
```

### 5.8 오류 처리 및 graceful degradation

| 상황 | 처리 방법 |
|------|-----------|
| MCP 서버 연결 실패 | 해당 서버의 도구를 LLM tools에서 제외, 로그 기록 |
| 도구 호출 타임아웃 | tool result에 오류 메시지 반환, LLM이 대안 응답 생성 |
| 도구 호출 응답 오류 | tool result에 오류 내용 포함, LLM에 전달 |
| 알 수 없는 도구 이름 | tool result에 "도구를 찾을 수 없습니다" 반환 |
| 모든 MCP 서버 장애 | tools 파라미터 없이 일반 대화 모드로 동작 |

핵심 원칙: **MCP 서버 장애가 전체 챗봇 장애로 이어지면 안 된다.** 도구를 사용할 수 없으면 도구 없이 일반 대화로 폴백한다.

### 5.9 MCP 관련 환경 변수

```text
MCP_ENABLED=false                        # 전역 활성화 플래그
MCP_SERVERS_JSON=[]                      # MCP 서버 목록 (JSON 배열)
MCP_TOOL_CACHE_TTL_SECONDS=300           # 도구 캐시 TTL (기본 5분)
MCP_TOOL_CALL_TIMEOUT_SECONDS=15         # 개별 도구 호출 타임아웃
MCP_DISCOVERY_TIMEOUT_SECONDS=10         # 도구 탐색 타임아웃
MCP_TOOL_SELECT_THRESHOLD=0.35           # 도구 선택 유사도 임계값
MCP_TOOL_SELECT_MAX_TOOLS=10             # 최대 선택 도구 수
MCP_TOOL_SELECT_KEYWORD_OVERRIDE=true    # 키워드 매칭 시 threshold 무시
```

### 5.10 도구 선택 전략 (Embedding 기반 Tool Filtering)

#### 5.10.1 문제: 도구 정의의 토큰 비용

LLM API에 `tools` 파라미터로 도구 정의를 전달하면, 각 도구의 이름·설명·파라미터 스키마가 context에 포함된다. 도구 하나당 약 **100~300 토큰**을 소비한다.

```text
예시: MCP 서버 5개, 서버당 평균 6개 도구 = 30개 도구
→ 30 × 200 = 약 6,000 토큰 (매 요청마다)

도구가 50개로 늘어나면:
→ 50 × 200 = 약 10,000 토큰 (매 요청마다)
```

대부분의 사용자 메시지는 일반 대화이며, 도구가 필요한 요청은 전체의 30~40% 정도다. 나머지 60~70%의 요청에서 도구 정의 토큰이 낭비된다.

#### 5.10.2 해결: 임베딩 유사도 기반 2단계 필터링

사용자 메시지의 임베딩과 도구 description 임베딩의 유사도를 비교하여, **도구 필요 여부 판단**과 **관련 도구 선택**을 하나의 연산으로 수행한다.

```text
┌─────────────────────────────────────────────────────────┐
│ 사용자 메시지 임베딩 (RAG 단계에서 이미 생성됨)           │
│          ↓                                               │
│  도구 description 임베딩 인덱스와 유사도 비교              │
│          ↓                                               │
│  ┌──────────────────────────────────────────────┐        │
│  │ max_similarity < TOOL_THRESHOLD (예: 0.35)   │        │
│  │  → 도구 불필요. tools=None으로 LLM 호출       │        │
│  │  → 토큰 절약: 도구 정의 0개 전달              │        │
│  ├──────────────────────────────────────────────┤        │
│  │ max_similarity ≥ TOOL_THRESHOLD              │        │
│  │  → threshold 이상인 도구만 선택               │        │
│  │  → 선택된 도구만 LLM에 전달 (보통 2~5개)      │        │
│  └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

핵심: RAG 검색을 위해 이미 생성한 사용자 메시지 임베딩을 **재사용**한다. 추가 임베딩 API 호출이 필요 없다.

#### 5.10.3 도구 임베딩 인덱스 구축

각 MCP 서버에서 도구 정의를 수집할 때(`tools/list`), 도구의 description을 임베딩하여 인덱스에 저장한다. 도구 캐시(§5.4)와 생명주기를 함께 한다.

```text
도구 임베딩 인덱스 구축 시점:
  1. 워커 시작 시 (도구 캐시 초기화와 동시)
  2. 캐시 TTL 만료 시 갱신 (도구 캐시와 동일한 주기)

인덱스 구조:
  tool_embeddings: list[ToolEmbedding]

  @dataclass
  class ToolEmbedding:
      tool_name: str           # 도구 이름 (예: "jira_create_issue")
      server_name: str         # 소속 MCP 서버 (예: "jira")
      description: str         # 도구 설명 원문
      embedding: list[float]   # description의 임베딩 벡터
```

임베딩 대상 텍스트는 도구의 `description` 필드를 기본으로 하되, 검색 품질을 높이기 위해 도구 이름과 파라미터 이름을 결합할 수 있다.

```text
임베딩 입력 텍스트 구성 예시:

방안 1: description만 사용 (단순)
  "Jira에 새 이슈를 생성합니다"

방안 2: name + description 결합 (권장)
  "jira_create_issue: Jira에 새 이슈를 생성합니다"

방안 3: name + description + parameters 결합 (정밀)
  "jira_create_issue: Jira에 새 이슈를 생성합니다. 파라미터: project, summary, description"
```

방안 2를 기본으로 시작하고, 실제 매칭 품질을 보며 조정한다.

#### 5.10.4 유사도 비교 흐름

```python
def select_tools(
    query_embedding: list[float],
    tool_embeddings: list[ToolEmbedding],
    threshold: float,
    max_tools: int = 10,
) -> list[str] | None:
    """
    사용자 메시지 임베딩과 도구 임베딩의 유사도를 비교하여
    관련 도구를 선택한다.

    Returns:
        관련 도구 이름 리스트. 도구가 불필요하면 None.
    """
    similarities = []
    for tool_emb in tool_embeddings:
        score = cosine_similarity(query_embedding, tool_emb.embedding)
        if score >= threshold:
            similarities.append((tool_emb.tool_name, score))

    if not similarities:
        return None  # 도구 불필요 → tools=None으로 LLM 호출

    # 유사도 높은 순 정렬, 상위 max_tools개 선택
    similarities.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in similarities[:max_tools]]
```

```text
예시 1: "안녕하세요, 오늘 기분이 좋아요"
  → 모든 도구와 유사도 < 0.35
  → return None → tools=None → 일반 대화 (토큰 절약)

예시 2: "ITC 프로젝트에서 이번 주 생성된 이슈 목록 보여줘"
  → "jira_search_issues" 유사도 0.82
  → "jira_create_issue" 유사도 0.51
  → "confluence_search" 유사도 0.28 (threshold 미만, 제외)
  → return ["jira_search_issues", "jira_create_issue"] → 2개만 LLM에 전달

예시 3: "서버 장애 현황 확인하고 관련 이슈 만들어줘"
  → "monitoring_check_status" 유사도 0.78
  → "jira_create_issue" 유사도 0.65
  → "monitoring_get_alerts" 유사도 0.61
  → return [...] → 3개만 전달 (여러 서버의 도구가 섞여도 정상 동작)
```

#### 5.10.5 RAG 임베딩 인프라 재사용

RAG(§4)에서 사용자 메시지를 임베딩하여 OpenSearch kNN 검색에 사용한다. 이 임베딩을 도구 선택에도 재사용하면 추가 비용이 없다.

```text
현재 (RAG만):
  user_message → [Embedding API 호출] → query_embedding → OpenSearch kNN

변경 후 (RAG + Tool Selection):
  user_message → [Embedding API 호출] → query_embedding
                                           ├→ OpenSearch kNN (RAG)
                                           └→ 도구 임베딩 유사도 비교 (Tool Selection)
```

임베딩 모델은 RAG와 동일한 모델을 사용한다. 도구 description 임베딩도 같은 모델로 생성해야 유사도 비교가 유의미하다.

단, **RAG가 비활성화(`RAG_ENABLED=false`)인 경우**에도 도구 선택은 독립적으로 동작해야 한다. 이 경우 도구 선택을 위해 별도로 임베딩 API를 호출한다.

```text
if RAG_ENABLED and MCP_ENABLED:
    query_embedding = embed(user_message)  # 1회 호출
    rag_context = opensearch_knn(query_embedding)
    selected_tools = select_tools(query_embedding, ...)

elif MCP_ENABLED only:
    query_embedding = embed(user_message)  # 도구 선택 전용 1회 호출
    selected_tools = select_tools(query_embedding, ...)

elif RAG_ENABLED only:
    query_embedding = embed(user_message)
    rag_context = opensearch_knn(query_embedding)
    # 도구 선택 불필요

else:
    # 기존 동작 (RAG 없음, MCP 없음)
```

#### 5.10.6 도구 임베딩 저장소

도구 임베딩은 **인메모리**로 관리한다. 도구 수는 보통 수십~수백 개 수준이므로 메모리 부담이 없다.

```text
도구 50개 × 임베딩 차원 1536 × float32(4 bytes) = 약 300KB
→ 메모리 부담 없음. 별도 DB 불필요.
```

도구 캐시(§5.4)가 갱신될 때 임베딩 인덱스도 함께 갱신한다.

```text
도구 캐시 갱신 흐름 (변경 후):
  1. MCP 서버에 tools/list 요청
  2. 도구 정의 파싱 → _tool_cache 업데이트
  3. [신규] 각 도구 description 임베딩 → _tool_embeddings 업데이트
  4. [신규] 역매핑 _tool_server_map 업데이트 (기존)
```

#### 5.10.7 Threshold 튜닝 전략

threshold가 너무 높으면 필요한 도구를 놓치고, 너무 낮으면 불필요한 도구를 포함한다.

```text
threshold 튜닝 가이드:

1. 초기값: 0.35 (보수적 — 도구를 놓치지 않는 방향)

2. 로그 기반 튜닝:
   - 도구 선택 결과를 로그에 기록 (메시지, 선택된 도구, 유사도 점수)
   - 실제 LLM이 tool_calls를 생성했는지 대조
   - False negative (도구가 필요했으나 선택 안 됨) → threshold 낮춤
   - False positive (불필요한 도구가 선택됨) → threshold 높임

3. 안전 장치:
   - 사용자 메시지에 명시적 키워드가 있으면 threshold 무시하고 포함
     예: "Jira" → jira 서버 도구 강제 포함
   - 유사도 점수가 전반적으로 낮지만 가장 높은 점수가
     soft_threshold(예: 0.25) 이상이면 상위 1~2개는 포함
```

```text
환경 변수:
  MCP_TOOL_SELECT_THRESHOLD=0.35         # 도구 선택 유사도 임계값
  MCP_TOOL_SELECT_MAX_TOOLS=10           # 최대 선택 도구 수
  MCP_TOOL_SELECT_KEYWORD_OVERRIDE=true  # 키워드 매칭 시 threshold 무시
```

#### 5.10.8 키워드 오버라이드 (Fallback 보완)

임베딩 유사도만으로는 놓칠 수 있는 경우를 키워드 매칭으로 보완한다.

```text
키워드 오버라이드 흐름:

1. 각 MCP 서버에 키워드 목록을 등록 (MCP_SERVERS_JSON에 추가)
   {
     "name": "jira",
     "url": "...",
     "keywords": ["jira", "이슈", "티켓", "지라"]
   }

2. 사용자 메시지에 키워드가 포함되면:
   - 해당 서버의 모든 도구를 후보에 추가
   - 임베딩 유사도 결과와 합집합

3. 최종 선택 도구 = 임베딩 선택 ∪ 키워드 선택
```

이 방식은 임베딩 모델이 도메인 용어(Jira, Confluence 등)를 잘 이해하지 못하는 경우에도 안정적으로 동작한다.

#### 5.10.9 토큰 절약 효과 추정

```text
시나리오: 도구 30개, 도구당 평균 200 토큰

AS-IS (모든 도구 전달):
  매 요청당 도구 토큰 = 30 × 200 = 6,000 토큰

TO-BE (임베딩 필터링):
  일반 대화 (60%): 도구 토큰 = 0
  도구 필요 (40%): 평균 3개 선택 = 3 × 200 = 600 토큰

  가중 평균 = 0.6 × 0 + 0.4 × 600 = 240 토큰/요청
  절약률 = (6,000 - 240) / 6,000 = 96%

  하루 1,000 요청 기준:
    AS-IS: 6,000,000 토큰 (도구 정의만)
    TO-BE:   240,000 토큰
    절약:  5,760,000 토큰/일
```

#### 5.10.10 패키지 구조 변경

```text
api/mcp/
├── __init__.py
├── client.py
├── registry.py
├── models.py             # ToolEmbedding dataclass 추가
├── tool_selector.py      # [신규] 임베딩 기반 도구 선택
└── errors.py
```

#### 5.10.11 llm/service.py 통합

```python
def generate_reply(*, history: list[dict], user_message: str) -> str:
    # 1. 사용자 메시지 임베딩 (RAG + 도구 선택 공용)
    query_embedding = _embed_query(user_message)

    # 2. RAG 검색
    rag_context = _retrieve_rag_context(user_message, query_embedding)

    # 3. 도구 선택 (임베딩 유사도 기반)
    selected_tool_names = _select_tools(query_embedding)
    tools = _get_mcp_tools(only=selected_tool_names)  # None이면 tools 파라미터 생략

    # 4. 메시지 배열 구성
    messages = _build_messages(
        history=history,
        user_message=user_message,
        rag_context=rag_context,
    )

    # 5. LLM 호출 (tools가 None이면 일반 대화, 있으면 에이전틱 루프)
    reply = _agentic_loop(messages=messages, tools=tools)
    return reply
```

---

## 6. 에이전틱 루프 (Agentic Loop)

### 6.1 개념

LLM이 도구를 호출하고, 그 결과를 보고 다시 도구를 호출하거나 최종 답변을 생성하는 반복 루프다.

```text
messages = [system, rag_context, history, user_message]
tools = [도구 정의 목록]
iteration = 0

while iteration < MAX_ITERATIONS:
    response = LLM.chat(messages, tools)

    if response.finish_reason == "stop":
        return response.content  ← 최종 답변

    if response.finish_reason == "tool_calls":
        for tool_call in response.tool_calls:
            result = mcp_client.call_tool(tool_call.name, tool_call.arguments)
            messages.append(assistant_message_with_tool_calls)
            messages.append({"role": "tool", "tool_call_id": ..., "content": result})

        iteration += 1
        continue

# 최대 반복 도달 시:
# tools를 제거하고 LLM에 한 번 더 호출 → 반드시 텍스트 응답 받음
```

### 6.2 안전 장치

| 장치 | 환경 변수 | 기본값 | 설명 |
|------|-----------|--------|------|
| 최대 반복 횟수 | `MCP_AGENTIC_MAX_ITERATIONS` | `5` | 무한 루프 방지 |
| 루프 전체 타임아웃 | `MCP_AGENTIC_TIMEOUT_SECONDS` | `60` | 전체 에이전틱 루프 시간 제한 |
| 개별 도구 타임아웃 | `MCP_TOOL_CALL_TIMEOUT_SECONDS` | `15` | 한 번의 도구 호출 시간 제한 |
| 개별 LLM 호출 타임아웃 | `LLM_TIMEOUT_SECONDS` | `30` | 기존 설정 재사용 |

최대 반복 도달 시 마지막까지 수집된 정보를 기반으로 LLM에 한 번 더 호출하되, 이때는 `tools`를 제거하여 반드시 텍스트 응답을 받는다.

### 6.3 대화 이력 저장 정책

에이전틱 루프 중간의 도구 호출/결과는 **대화 이력에 저장하지 않는다**. 저장 대상은 다음 두 가지만이다.

- 사용자 메시지 (`role: "user"`)
- 최종 LLM 텍스트 응답 (`role: "assistant"`)

이유:
- 도구 호출 메시지가 이력에 들어가면 다음 요청에서 LLM에 불필요한 맥락이 전달된다.
- 이력 크기가 빠르게 증가한다.
- `tool` role 메시지는 해당 `tool_call_id`가 없는 후속 요청에서 오류를 유발할 수 있다.

도구 호출 기록이 필요하면 별도 activity 로그에 남긴다.

---

## 7. llm/service.py 변경 설계

### 7.1 외부 인터페이스 유지

```python
# 현재 시그니처 — 변경하지 않는다
def generate_reply(*, history: list[dict], user_message: str) -> str:
```

외부 호출 인터페이스를 변경하지 않는 것이 중요하다. `cube/service.py`의 `process_incoming_message()`는 수정 없이 그대로 동작해야 한다.

### 7.2 내부 구조 변경

```python
def generate_reply(*, history: list[dict], user_message: str) -> str:
    # 1. RAG 검색 (RAG_ENABLED=true일 때만)
    rag_context = _retrieve_rag_context(user_message)

    # 2. MCP 도구 정의 수집 (MCP_ENABLED=true일 때만)
    tools = _get_mcp_tools()

    # 3. 메시지 배열 구성 (RAG 문맥 포함)
    messages = _build_messages(
        history=history,
        user_message=user_message,
        rag_context=rag_context,
    )

    # 4. 에이전틱 루프 (tools가 있으면 루프, 없으면 단일 호출)
    reply = _agentic_loop(messages=messages, tools=tools)

    return reply
```

### 7.3 _build_messages 변경

```python
def _build_messages(
    *,
    history: list[dict],
    user_message: str,
    rag_context: str = "",       # 신규 파라미터
) -> list[dict]:
    messages = []

    system_prompt = get_system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # [신규] RAG 문맥 주입
    if rag_context:
        messages.append({"role": "system", "content": rag_context})

    # 대화 이력 (기존 로직 동일)
    for item in history:
        ...

    messages.append({"role": "user", "content": user_message.strip()})
    return messages
```

### 7.4 LLM 응답 처리 변경

현재 `_extract_reply_text()`는 `choices[0].message.content`만 추출한다. 변경 후에는 `tool_calls` 필드도 확인해야 한다.

```python
def _extract_response(response: dict) -> dict:
    """
    LLM 응답에서 message 전체를 추출한다.
    content와 tool_calls를 모두 포함할 수 있다.
    """
    choice = response["choices"][0]
    return {
        "finish_reason": choice.get("finish_reason", "stop"),
        "content": choice["message"].get("content"),
        "tool_calls": choice["message"].get("tool_calls"),
    }
```

---

## 8. MCP 서버 구축 가이드라인

이 섹션은 별도 저장소에서 MCP 도구 서버를 구축하는 동료를 위한 가이드다.

### 8.1 기본 원칙

- 각 MCP 서버는 **하나의 도메인**(Jira, Confluence, 모니터링 등)을 담당한다.
- **별도 저장소, 별도 배포, 별도 URL**로 운영한다.
- MCP 프로토콜 표준을 준수하여 이 챗봇 외의 다른 MCP 클라이언트(Claude Desktop, Cursor 등)에서도 사용 가능하게 한다.

### 8.2 권장 기술 스택

```text
- 언어: Python 3.11+
- 프레임워크: MCP Python SDK (mcp 패키지)
  - FastMCP 클래스를 사용하면 최소 코드로 MCP 서버 구현 가능
- 전송: Streamable HTTP (SSE)
- 배포: 컨테이너 (Docker), 서비스별 독립 URL
- 설치: pip install "mcp[cli]"
```

### 8.3 최소 구현 예시

```python
# mcp_jira_server/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jira-tools")

@mcp.tool()
def create_issue(project: str, summary: str, description: str = "") -> str:
    """Jira에 새 이슈를 생성합니다.

    Args:
        project: 프로젝트 키 (예: "ITC")
        summary: 이슈 제목
        description: 이슈 설명 (선택)
    """
    # Jira REST API 호출 로직
    issue_key = call_jira_api(project, summary, description)
    return f"이슈 {issue_key} 생성 완료"

@mcp.tool()
def search_issues(query: str, max_results: int = 10) -> str:
    """JQL로 Jira 이슈를 검색합니다.

    Args:
        query: JQL 검색 쿼리
        max_results: 최대 결과 수
    """
    results = call_jira_search(query, max_results)
    return format_results(results)

if __name__ == "__main__":
    mcp.run(transport="sse")
```

`@mcp.tool()` 데코레이터가 함수의 docstring과 타입 힌트를 자동으로 MCP 도구 정의(JSON Schema)로 변환한다. 별도로 스키마를 작성할 필요가 없다.

### 8.4 각 MCP 서버가 구현해야 할 인터페이스

| 메서드 | 설명 | 필수 |
|--------|------|------|
| `initialize` | 서버 초기화 및 capability 교환 | 필수 (SDK가 자동 처리) |
| `tools/list` | 사용 가능한 도구 목록 반환 | 필수 |
| `tools/call` | 특정 도구 실행 | 필수 |
| `resources/list` | 리소스 목록 | 선택 |
| `prompts/list` | 프롬프트 목록 | 선택 |

최소한 `tools/list`와 `tools/call`만 구현하면 이 챗봇과 연동할 수 있다. MCP Python SDK의 `FastMCP`를 사용하면 위 인터페이스를 자동으로 제공한다.

### 8.5 도구 설계 권장사항

```text
도구 이름:
  - 서버 도메인 접두사 권장: jira_create_issue, confluence_search
  - 이유: 서로 다른 MCP 서버 간 도구 이름 충돌 방지

도구 설명:
  - 한국어로 작성 (LLM이 한국어 사용자를 대상으로 동작)
  - LLM이 "언제 이 도구를 써야 하는지" 판단할 수 있도록 구체적으로 작성

파라미터:
  - 타입 힌트 필수 (str, int, bool 등)
  - 기본값이 있는 파라미터는 선택 파라미터로 노출
  - 복잡한 입력보다 단순한 문자열/숫자 파라미터 권장

반환값:
  - 항상 문자열로 반환
  - LLM이 읽기 쉬운 형태로 포맷팅 (JSON dump보다 사람이 읽기 쉬운 텍스트)
  - 에러 발생 시에도 문자열로 에러 메시지 반환 (예외를 던지지 않음)
```

### 8.6 MCP 서버 프로젝트 구조 (권장)

```text
mcp-jira-server/
├── README.md
├── requirements.txt        # mcp[cli], requests 등
├── Dockerfile
├── .env.example
├── server.py               # FastMCP 진입점
└── tools/
    ├── __init__.py
    ├── issues.py            # 이슈 관련 도구
    └── projects.py          # 프로젝트 관련 도구
```

간단한 서버는 `server.py` 하나로 충분하다. 도구가 많아지면 `tools/` 패키지로 분리한다.

### 8.7 배포 모델

```text
MCP 서버 A (Jira)        → 컨테이너 A → https://mcp-jira.internal/
MCP 서버 B (Confluence)   → 컨테이너 B → https://mcp-confluence.internal/
MCP 서버 C (Monitoring)   → 컨테이너 C → https://mcp-monitoring.internal/

LLM Chatbot               → 기존 컨테이너 → MCP 클라이언트로서 위 서버들에 연결
```

새 MCP 서버를 추가하려면:
1. 새 저장소에서 MCP 서버 구현
2. 컨테이너 배포, URL 확보
3. 챗봇의 `MCP_SERVERS_JSON`에 새 서버 항목 추가
4. 챗봇이 자동으로 새 서버의 도구를 탐색

**챗봇 코드를 수정할 필요가 없다.**

### 8.8 로컬 테스트

MCP Python SDK에는 테스트용 Inspector가 포함되어 있다.

```bash
# MCP 서버를 로컬에서 테스트
mcp dev server.py

# Inspector UI가 열리면 tools/list, tools/call을 수동 테스트 가능
```

---

## 9. 기존 코드 영향 분석

### 9.1 수정이 필요한 파일

| 파일 | 변경 내용 |
|------|-----------|
| `api/config.py` | RAG, MCP 관련 환경 변수 추가 |
| `api/llm/service.py` | RAG 문맥 주입, 도구 정의 전달, 에이전틱 루프 구현 |
| `requirements.txt` | `opensearch-py` 추가 |

### 9.2 수정하지 않는 파일

| 파일 | 이유 |
|------|------|
| `api/cube/router.py` | 요청 수신 경로 변경 없음 |
| `api/cube/service.py` | `generate_reply()` 시그니처 유지 |
| `api/cube/worker.py` | 기존 worker 루프 그대로 |
| `api/cube/queue.py` | 큐 구조 변경 없음 |
| `api/conversation_service.py` | 도구 호출은 이력에 저장하지 않음 |

### 9.3 신규 파일

| 파일 | 역할 |
|------|------|
| `api/rag/__init__.py` | RAG 패키지 공개 인터페이스 |
| `api/rag/retriever.py` | OpenSearch / 외부 API 검색 로직 |
| `api/mcp/__init__.py` | MCP 패키지 공개 인터페이스 |
| `api/mcp/client.py` | MCP 클라이언트 핵심 로직 |
| `api/mcp/registry.py` | MCP 서버 등록 정보 관리 |
| `api/mcp/models.py` | MCP 관련 dataclass |
| `api/mcp/errors.py` | MCP 관련 예외 |
| `api/mcp/tool_selector.py` | 임베딩 기반 도구 필요 여부 판단 + 관련 도구 선택 |
| `tests/test_rag_retriever.py` | RAG 검색 테스트 |
| `tests/test_mcp_client.py` | MCP 클라이언트 테스트 |
| `tests/test_agentic_loop.py` | 에이전틱 루프 테스트 |

---

## 10. 구현 단계

### Phase 1. 기반 구조

목표: 코드 구조만 추가하고, `RAG_ENABLED=false`, `MCP_ENABLED=false`로 기존 동작을 유지한다.

- `api/rag/` 패키지 생성, `retrieve_context()` 스텁 구현 (항상 빈 결과 반환)
- `api/mcp/` 패키지 생성, 서버 레지스트리와 도구 캐시 스텁 구현
- `api/config.py`에 RAG/MCP 환경 변수 추가
- `api/llm/service.py`에 RAG 문맥 수신 경로와 에이전틱 루프 골격 추가
- 비활성화 상태에서 기존 동작이 동일한지 테스트 검증

### Phase 2. RAG 연동

목표: 지식 베이스 검색이 실제로 동작하여 LLM 응답에 맥락을 제공한다.

- OpenSearch 기반 retriever 구현 (kNN 벡터 검색)
- RAG 문맥 포맷팅 및 system prompt 주입
- 외부 검색 API 보강 경로 추가 (선택)
- `RAG_ENABLED=true` 설정으로 활성화
- RAG 검색 결과 로깅

### Phase 3. MCP 클라이언트 연동

목표: 외부 MCP 서버의 도구를 LLM에 제공하고, 도구 호출이 실제로 동작한다.

- MCP 서버 도구 탐색 구현 (httpx 기반)
- 도구 정의 캐시 구현 (TTL 기반)
- MCP → OpenAI tools 형식 변환
- 도구 호출 라우팅 구현
- 에이전틱 루프 전체 구현
- `MCP_ENABLED=true` 설정으로 활성화

### Phase 4. 안정화 및 관측성

목표: 운영 환경에서 안정적으로 동작한다.

- 에이전틱 루프 안전 장치 검증 (최대 반복, 타임아웃)
- MCP 서버 장애 시 graceful degradation 검증
- activity 로그에 RAG/MCP 관련 정보 추가
- uWSGI harakiri 타임아웃과 에이전틱 루프 타임아웃 조율

### Phase 5. MCP 서버 확장

목표: 실제 업무 도구를 MCP 서버로 구축하여 연동한다.

- 첫 번째 MCP 서버 구축 (가장 효용이 높은 도메인 선택)
- 챗봇에 서버 URL 등록, 실사용자 테스트
- 추가 MCP 서버 점진적 확장

---

## 11. 목표 파일 구조

```text
llm_chatbot/
├── api/
│   ├── __init__.py
│   ├── config.py                    # [수정] RAG, MCP 환경 변수 추가
│   ├── conversation_service.py
│   ├── cube/
│   │   └── (변경 없음)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── service.py               # [수정] RAG 주입, 에이전틱 루프
│   │   └── prompt/
│   ├── rag/                          # [신규]
│   │   ├── __init__.py
│   │   └── retriever.py
│   ├── mcp/                          # [신규]
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── registry.py
│   │   ├── models.py
│   │   ├── tool_selector.py          # [신규] 임베딩 기반 도구 선택
│   │   └── errors.py
│   ├── cdn/
│   └── utils/
├── tests/
│   ├── test_rag_retriever.py         # [신규]
│   ├── test_mcp_client.py            # [신규]
│   └── test_agentic_loop.py          # [신규]
└── doc/
    └── RAG_MCP_아키텍처.md           # 이 문서
```

---

## 12. 주의사항

### 12.1 LLM 모델의 도구 호출 지원 검증

현재 사용 중인 LLM(Kimi-K2.5, Qwen3, GPT-OSS 등)이 OpenAI 호환 `tool_calls` 형식을 지원하는지 **사전 확인이 필수**다.

확인 방법: LLM API에 `tools` 파라미터를 포함한 요청을 보내 응답에 `tool_calls`가 오는지 테스트한다.

```json
{
  "model": "Kimi-K2.5",
  "messages": [{"role": "user", "content": "서울 날씨 알려줘"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "도시의 현재 날씨를 조회합니다",
      "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
      }
    }
  }]
}
```

응답에 `"tool_calls": [{"function": {"name": "get_weather", ...}}]`가 포함되면 지원 확인 완료다. 모델이 지원하지 않으면 MCP 도구 연동이 동작하지 않는다.

참고: Qwen3, Kimi-K2.5는 function calling을 지원하는 것으로 알려져 있으나, 사내 배포 버전에서의 지원 여부는 별도 확인이 필요하다.

### 12.2 비동기 워커 타임아웃

에이전틱 루프에서 여러 도구를 순차 호출하면 한 메시지 처리 시간이 길어질 수 있다.

- uWSGI `harakiri` 타임아웃 (현재 120초)
- `MCP_AGENTIC_TIMEOUT_SECONDS` (기본 60초)
- `LLM_TIMEOUT_SECONDS` (기본 30초)

harakiri > 에이전틱 루프 타임아웃 > 개별 호출 타임아웃 순서로 설정해야 한다.

### 12.3 도구 이름 충돌

서로 다른 MCP 서버가 같은 이름의 도구를 제공할 수 있다. 방지 방법:

- 도구 이름에 서버 접두사 권장 (예: `jira_create_issue`, `confluence_search`)
- MCP 클라이언트 레벨에서 충돌 감지 시 로그 경고 및 나중에 등록된 도구 무시

### 12.4 다중 LLM 라우팅과의 관계

`doc/다중_LLM_동적_라우팅_구현_계획.md`에서 계획 중인 모델 레지스트리, provider adapter, resolver 구조와 이 RAG/MCP 설계는 독립적으로 구현 가능하다.

다중 LLM 라우팅이 먼저 구현되면, resolved model의 도구 호출 지원 여부에 따라 MCP 활성화를 동적으로 결정할 수 있다 (도구 호출을 지원하지 않는 모델로 라우팅된 경우 tools 파라미터 생략).
