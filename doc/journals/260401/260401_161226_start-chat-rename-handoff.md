# general_chat → start_chat 리네이밍 + Handoff 구현

**날짜**: 2026-04-01  
**세션 요약**: Approach A 채택 — start_chat이 진입점 겸 일반 대화 처리, handoff로 전용 워크플로 전환

---

## 1. 진행 사항

### 아키텍처 논의
- **Approach A** vs **B** 비교 — A 채택 (start_chat = classify + casual 직접 처리 + handoff)
- `casual_chat` 별도 워크플로 불필요 판단 — 일반 대화는 stateless, 워크플로는 stateful로 구분

### 디렉토리 리네이밍 (Phase 1)
- `api/workflows/general_chat/` → `api/workflows/start_chat/` (`git mv`)
- 패키지 내부 13개 파일 import/이름/docstring 전체 업데이트
- `GeneralChatWorkflowState` → `StartChatWorkflowState`
- 함수명: `execute_general_chat_plan` → `execute_start_chat_plan` 등
- 상수명: `GENERAL_CHAT_*` → `START_CHAT_*`
- `from __future__ import annotations` 전체 제거

### classify 노드 분기 로직 (Phase 2)
- `classify_intent_node`: `determine_handoff_workflow()` 결과에 따라 casual(resume) vs specific(handoff) 분기
- `entry_node`, `retrieve_context_node`, `plan_response_node`: action을 `"wait"` → `"resume"`으로 변경 (단일 호출 체이닝)
- `generate_reply_node`: action을 `"complete"`로 변경

### 오케스트레이터 handoff 처리 (Phase 3)
- `_handle_handoff()` 신규 함수: 스택에 현재 위치 저장 → 대상 워크플로 실행 → 완료 시 스택 복귀
- `run_graph()`에 `action=="handoff"` 분기 추가
- 재귀적 `run_graph()` 호출로 대상 워크플로 실행

### 테스트 (Phase 4)
- `tests/test_start_chat_workflow.py` 신규 (12개 테스트)
- 전체 93개 테스트 통과 (기존 80 + start_chat 12 + 이전 세션 sample 1개 추가)

---

## 2. 수정 내용

### 디렉토리 이동
- `api/workflows/general_chat/` → `api/workflows/start_chat/`

### 수정된 파일
| 파일 | 변경 |
|------|------|
| `api/workflows/start_chat/state.py` | 클래스명, default, `from __future__` 제거 |
| `api/workflows/start_chat/graph.py` | import 경로, workflow_id |
| `api/workflows/start_chat/nodes.py` | import 경로, 분기 로직, action 변경 |
| `api/workflows/start_chat/routing.py` | import 경로, getattr 안전 접근 |
| `api/workflows/start_chat/prompts.py` | 상수명 변경 |
| `api/workflows/start_chat/agent/executor.py` | import, 함수명, getattr 안전 접근 |
| `api/workflows/start_chat/agent/planner.py` | import, 함수명 |
| `api/workflows/start_chat/rag/retriever.py` | 함수명 |
| `api/workflows/start_chat/rag/context_builder.py` | 함수명 |
| `api/workflows/registry.py` | import, 키/값, `from __future__` 제거 |
| `api/workflows/orchestrator.py` | DEFAULT_WORKFLOW_ID + `_handle_handoff()` 추가 |
| `doc/랭그래프_api_구조_계획.md` | general_chat → start_chat 치환 |

### 신규 파일
| 파일 | 설명 |
|------|------|
| `tests/test_start_chat_workflow.py` | start_chat + handoff 테스트 12개 |

---

## 3. 다음 단계

- **Cube 파이프라인 연결**: `cube/service.py`에서 `generate_reply()` 대신 `orchestrator.handle_message()` 호출
- **classify 노드 실제 구현**: LLM 호출로 사용자 의도 분류 (현재는 스텁)
- **전용 워크플로 노드 구현**: chart_maker, ppt_maker 등에 실제 MCP 도구 호출 추가
- **translate 워크플로 추가**: sample에서 검증한 번역 도구를 실제 워크플로로 승격

---

## 4. 메모리 업데이트

`general_chat` → `start_chat` 리네이밍 반영, Approach A 결정 기록.
