---
tags: [concept, workflow, langgraph, runtime]
level: intermediate
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/workflows.md
  - api/workflows/lg_orchestrator.py
  - api/workflows/start_chat/lg_graph.py
  - api/workflows/registry.py
  - api/workflows/langgraph_checkpoint.py
---

# 워크플로 런타임 구조 (Workflow Runtime Structure)

> 이 저장소는 "워크플로마다 별도 엔진"이 아니라 `start_chat` 루트 그래프 하나에 업무용 서브그래프를 붙여 두는 단일 LangGraph 런타임이다.

## 왜 필요한가? (Why)

- Cube 채널과 웹 채널 모두 같은 진입점(orchestrator)을 거치므로, 진입점이 하나여야 멀티턴 복원과 운영 관점이 단순해진다.
- 업무 의도가 감지되면 그때만 서브그래프로 분기하기 위해 "라우터 + 슬롯필링" 패턴이 필요하다.
- LangGraph 의 `interrupt/resume` 기반 멀티턴 흐름은 별도 세션 저장 코드를 줄여 준다.
- 비슷한 다른 개념과의 차이: 이 저장소는 워크플로별 별도 프로세스/엔진을 두지 않으며, 라우팅·실행·상태 모두 하나의 컴파일된 LangGraph 안에서 처리한다.

## 핵심 개념 (What)

### 정의

이 저장소의 워크플로 런타임은 "`start_chat` 루트 그래프 + 업무별 서브그래프 + thread 단위 checkpointer 기반 interrupt/resume" 모델이다 (`raw/learning-logs/workflows.md` §1, §10).

### 관련 용어

- `오케스트레이터(Orchestrator)`: `api/workflows/lg_orchestrator.py` 의 `handle_message()`. Cube/웹 입력을 받아 컴파일된 루트 그래프를 호출한다.
- `루트 그래프(Root Graph)`: `api/workflows/start_chat/lg_graph.py` 가 빌드하는 `start_chat` LangGraph. 일반 대화 + 라우터 역할을 동시에 수행한다.
- `서브그래프(Subgraph)`: 업무형 워크플로 (`translator` 등) 가 컴파일되어 루트 그래프의 노드로 들어가는 형태.
- `handoff_keywords`: 루트 그래프의 `classify_node` 가 사용자 메시지를 보고 어떤 서브그래프로 넘길지 판단하는 키워드 목록 (`workflow_id` 별 메타데이터).
- `interrupt / Command(resume=...)`: LangGraph 멀티턴 일시정지·재개 메커니즘. 누락 슬롯 수집에 사용된다.
- `checkpointer`: thread 단위로 중간 상태를 저장하는 컴포넌트. Mongo 가 있으면 `MongoDBSaver`, 없으면 `MemorySaver` (`api/workflows/langgraph_checkpoint.py`).
- `thread id`: `user_id::channel_id`. 사용자+채널 단위로 하나의 대화 thread 를 유지한다.

### 시각화 / 모델

```text
Cube/Web 입력
    │
    ▼
api/cube/router.py  ──►  큐/워커
                              │
                              ▼
              api/workflows/lg_orchestrator.py
                  handle_message()  (컴파일 1회 후 캐시)
                              │
                              ▼
                   start_chat 루트 그래프
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
          retrieve_context  classify    (handoff)
                │             │             │
                ▼             ▼             ▼
          generate_reply   END         translator 등 서브그래프
                                            │
                                       interrupt({"reply": ...})
                                            │  (다음 사용자 메시지)
                                            ▼
                                     Command(resume=user_input)
```

## 어떻게 사용하는가? (How)

### 최소 예제

루트 그래프는 한 번만 컴파일되어 캐시된다. 새 사용자 메시지가 오면 같은 그래프를 thread id 별로 호출한다.

```python
# api/workflows/lg_orchestrator.py 의 흐름 (개념도)
graph = build_start_chat_graph().compile(checkpointer=checkpointer)
result = graph.invoke(
    {"user_message": text, "user_id": uid, "channel_id": cid},
    config={"configurable": {"thread_id": f"{uid}::{cid}"}},
)
```

### 실무 패턴

- **루트 = 라우터 + 일반 대화**: `start_chat` 의 `entry_node → classify_node → retrieve_context_node → generate_reply_node` 경로가 일반 질의 답변을 처리하고, 업무 의도면 `_route_after_classify()` 가 서브그래프로 분기한다 (`raw/learning-logs/workflows.md` §4.1).
- **interrupt/resume 으로 슬롯 수집**: `translator` 가 전형적인 예. 원문/목표 언어가 없으면 `collect_*_node` 에서 `interrupt({"reply": ...})` → 사용자 응답이 오면 `Command(resume=...)` 으로 재개 (`raw/learning-logs/workflows.md` §4.2).
- **thread 는 워크플로별이 아니라 사용자+채널 단위**: 워크플로별 thread 분리는 하지 않는다. 루트 그래프가 하나여서 자연스럽다 (`raw/learning-logs/workflows.md` §2.3).
- **서브그래프는 레지스트리에서 자동 등록**: `start_chat` 빌더가 `list_handoff_workflows()` 결과를 읽어 서브그래프로 컴파일해 붙인다 (`api/workflows/registry.py`, `raw/learning-logs/workflows.md` §2.4).

### 주의사항 / 함정

- **루트 그래프는 1회 컴파일 + 캐시**: `_compiled_graph` 단일 캐시이므로 새 워크플로 추가나 handoff metadata 변경은 사실상 프로세스 재시작이 필요하다. 런타임 중 registry reload 를 기대하면 안 된다 (`raw/learning-logs/workflows.md` §8.3).
- **`start_chat` 은 레지스트리에 등록되지 않음**: 루트 그래프이지만 `/workflows` 시각화 목록에는 빠진다. 새 팀원이 헷갈리는 포인트 (`raw/learning-logs/workflows.md` §8.1).
- **상태 정의가 두 층**: LangGraph 런타임 상태는 `TypedDict` 기반 (`api/workflows/lg_state.py` `ChatState`), 레지스트리/구버전 호환용 `WorkflowState` dataclass 가 별도로 남아 있다. devtools 호환 때문 (`raw/learning-logs/workflows.md` §3.3).
- **모든 handoff 워크플로를 루트에 직접 붙이는 구조는 비대해진다**: 워크플로 수가 늘면 컴파일 시간·메모리·디버깅 비용이 같이 늘어난다 → [workflow-routing-scaling.md](workflow-routing-scaling.md) 참고.

> Unverified: orchestrator 의 단일 컴파일 캐시가 정확히 `_compiled_graph` 라는 식별자로 존재하는지는 raw 메모를 옮겨 적은 것으로, 코드에서 직접 확인되지 않았다. `api/workflows/lg_orchestrator.py` 를 열어 캐시 변수명을 확인할 것.

## 참고 자료 (References)

- 원본 메모: [../../raw/learning-logs/workflows.md](../../raw/learning-logs/workflows.md)
- 관련 개념:
  - [workflow-registration.md](workflow-registration.md) — 워크플로 등록 계약
  - [workflow-state-management.md](workflow-state-management.md) — 상태 분리 원칙
  - [workflow-authoring.md](workflow-authoring.md) — 새 워크플로 만드는 법
  - [workflow-prompting.md](workflow-prompting.md) — `prompts.py` 규칙
  - [workflow-routing-scaling.md](workflow-routing-scaling.md) — 라우팅 확장 전략
- 코드 경로:
  - `api/workflows/lg_orchestrator.py`
  - `api/workflows/start_chat/lg_graph.py`
  - `api/workflows/registry.py`
  - `api/workflows/langgraph_checkpoint.py`
  - `api/workflows/lg_state.py`
- 외부 문서: LangGraph Subgraphs — <https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
