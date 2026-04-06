## 1. 진행 사항
- MCP 도구가 많아질 때 LLM 성능이 저하되는 "too many tools" 문제를 조사했다.
- 현재 코드베이스의 MCP 구조(`api/mcp/`)를 분석했다: `tool_selector.py`가 스텁 상태(필터링 없이 전체 반환).
- 학술 논문, 업계 사례, MCP 공식 문서를 종합해 5가지 접근법을 정리했다.
- 우리 워크플로 아키텍처(`api/workflows/orchestrator.py`)와의 통합 전략을 도출했다.

## 2. 핵심 문제: MCP 도구 과다 노출

LLM은 도구가 **20개를 넘으면** 선택 정확도가 눈에 띄게 떨어지고, **30개 이상**에서는 설명이 겹치면서 혼란이 심해진다. 100개 이상이면 사실상 올바른 도구 선택이 불가능하다.

**현재 우리 코드의 문제점:**
- `tool_selector.py`의 `select_tools()`가 필터링 없이 전체 도구를 반환 중
- 워크플로별 도구 스코핑이 없음
- 도구가 늘어날수록 토큰 낭비 + 정확도 하락이 예상됨

## 3. 접근법 비교

### 접근법 A: 스키마 압축 (Schema Compression)

도구 정의에서 description, enum, 중첩 문서를 제거하고 파라미터 구조만 유지.

| 항목 | 내용 |
|------|------|
| 토큰 절감 | 70-97% |
| 구현 비용 | 낮음 (프록시 수준) |
| 단점 | 유사한 도구 간 구분력 저하 |
| 적합 | 도구 50개 미만, 빠른 개선이 필요할 때 |

### 접근법 B: Search-First Discovery (검색 우선 탐색)

전체 스키마를 미리 로딩하지 않고, 메타 도구 3개로 on-demand 탐색:
1. **`search_tools`** — 임베딩 기반 시맨틱 검색으로 후보 탐색
2. **`describe_tools`** — 선택된 도구의 상세 스키마만 로딩
3. **`execute_tool`** — 실행

```
사용자 메시지 → search_tools → 후보 목록 → describe_tools → 스키마 로딩 → execute_tool
```

| 항목 | 내용 |
|------|------|
| 토큰 절감 | 91-97% (입력), 90% (전체) |
| 도구 선택 정확도 | 49% → 74% (Claude Opus 4), 79.5% → 88.1% (Opus 4.5) |
| 단점 | 라운드트립 50% 증가, 2-3배 더 많은 tool call |
| 적합 | 도구 50개 이상, 대규모 API 카탈로그 |

**Speakeasy의 실측 결과:** 도구 40개든 400개든 초기 토큰 사용량이 1,300-2,500으로 일정. 160배 토큰 절감 달성.

### 접근법 C: Dynamic ReAct (논문 기반)

5가지 아키텍처를 실험한 학술 논문(arxiv 2509.20386)의 결론:

| 아키텍처 | 설명 | 결과 |
|---------|------|------|
| Direct Semantic Search | 쿼리 직접 벡터 검색 | 정확도 낮음 |
| Meta-Tool Query | LLM이 검색 쿼리 구성 | 개선됨 |
| **Search and Load (권장)** | search(k1=20) → 앱당 cap(k2=5) → load | **도구 로딩 50% 감소, 정확도 유지** |
| Hierarchical Search | app 검색 → tool 검색 → load | 오버헤드 대비 이득 적음 |
| Fixed Tool Set | 고정 메타도구로 동적 접근 | 긴 대화에서 성능 저하 |

**핵심 인사이트:**
- Voyage-context-3 임베딩 + Claude Sonnet 컨텍스트 보강 → Top-5 정확도 60% (baseline 40% 대비 50% 향상)
- 하이브리드 검색(시맨틱+BM25)은 키워드 겹침으로 오히려 정확도 하락 → **벡터 전용** 권장
- "항상 사용 가능한" 기본 도구(web_search 등)는 별도 관리해야 불필요한 검색 방지

### 접근법 D: 워크플로 기반 도구 스코핑 (LangGraph Dynamic Tool Calling)

LangGraph의 공식 기능: 워크플로의 각 단계(노드)마다 사용 가능한 도구를 다르게 바인딩.

```python
# 개념적 예시: 노드별 도구 바인딩
def classify_node(state, message):
    # 분류 단계에서는 도구 불필요
    ...

def execute_node(state, message):
    # 실행 단계에서는 해당 워크플로의 도구만 바인딩
    tools = select_tools_for_workflow(state.workflow_id)
    llm_with_tools = llm.bind_tools(tools)
    ...
```

| 항목 | 내용 |
|------|------|
| 토큰 절감 | 워크플로 범위에 따라 다름 |
| 구현 비용 | 중간 (워크플로 정의에 도구 매핑 추가) |
| 장점 | 워크플로 컨텍스트에 정확히 맞는 도구만 노출, 인증/권한 연동 자연스러움 |
| 적합 | 우리처럼 워크플로 기반 아키텍처가 이미 있는 경우 |

### 접근법 E: Code-Based Execution (코드 모드)

에이전트가 코드를 작성해 샌드박스에서 실행, 결과를 필터링한 뒤 반환. 도구 2개만 노출.

| 항목 | 내용 |
|------|------|
| 토큰 절감 | 98-99% (스키마 + 응답 모두) |
| 정확도 | Sonnet 4.6 기준 42% → 80% |
| 단점 | 샌드박스 인프라 필요, 코드 생성 정확도 의존 |
| 적합 | 대규모 API + 큰 응답 페이로드가 공존할 때 |

## 4. 우리 프로젝트 적용 전략 제안

현재 아키텍처를 활용한 **단계적 적용 로드맵:**

### Phase 1: 워크플로 기반 도구 스코핑 (즉시 적용 가능)

우리는 이미 워크플로 레지스트리(`api/workflows/registry.py`)와 MCP 도구 선택기(`api/mcp/tool_selector.py`)를 갖고 있다.

**구현 방향:**
```
WorkflowDefinition에 "tools" 또는 "tool_tags" 필드 추가
  ↓
tool_selector.select_tools()가 workflow_id 기반 필터링
  ↓
각 노드에서 해당 워크플로의 도구만 LLM에 전달
```

- `WorkflowDefinition`에 `tool_ids: list[str]` 또는 `tool_tags: list[str]` 추가
- `select_tools()`가 `workflow_id`로 워크플로 정의를 조회해 해당 도구만 반환
- `MCPTool` 모델에 `tags: list[str]` 필드 추가 (카테고리 분류용)
- 노드별 도구 바인딩: 분류 노드는 도구 없이, 실행 노드만 도구 바인딩

### Phase 2: 시맨틱 검색 기반 필터링 (도구 30개 이상 시)

- 도구 description 임베딩을 사전 계산하여 캐시
- `select_tools()`에 `user_message` 기반 시맨틱 유사도 필터링 추가
- top-k (k=10~15) 도구만 LLM에 전달
- `api/mcp/cache.py`의 기존 캐시 인프라 활용

### Phase 3: Search-First Discovery (도구 100개 이상 시)

- 메타 도구 패턴 도입: `search_tools` → `describe_tools` → `execute_tool`
- 스키마 lazy loading으로 토큰 절감 극대화
- MCP 서버 `notifications/tools/list_changed` 프로토콜 활용

## 5. 참고 자료

- [Speakeasy — Reducing MCP token usage by 100x](https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2)
- [Dynamic ReAct: Scalable Tool Selection (arxiv 2509.20386)](https://arxiv.org/abs/2509.20386)
- [Speakeasy — Dynamic Tool Discovery in MCP](https://www.speakeasy.com/mcp/tool-design/dynamic-tool-discovery)
- [StackOne — MCP Token Optimization: 4 Approaches Compared](https://www.stackone.com/blog/mcp-token-optimization/)
- [LangGraph — Dynamic Tool Calling](https://changelog.langchain.com/announcements/dynamic-tool-calling-in-langgraph-agents)
- [MCP Specification — Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [Cline Discussion — Dynamic Tool Filtering using Embedding](https://github.com/cline/cline/discussions/3081)

## 6. 다음 단계
- Phase 1의 `WorkflowDefinition` 도구 매핑 설계 구체화
- `MCPTool` 모델에 `tags` 필드 추가 여부 결정
- `tool_selector.py` 스텁을 실제 워크플로 기반 필터링으로 교체
- 도구 수 증가 시점에 Phase 2 시맨틱 검색 도입 판단 기준 정하기

## 7. 메모리 업데이트
- 변경 없음 (연구 단계, 구현 결정 전)
