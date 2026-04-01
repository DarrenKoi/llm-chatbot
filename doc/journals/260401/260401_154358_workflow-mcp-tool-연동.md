# 워크플로 ↔ MCP 도구 연동 구현

**날짜**: 2026-04-01  
**세션 요약**: 워크플로 노드가 MCP 도구를 호출하는 전체 파이프라인 구현 및 검증

---

## 1. 진행 사항

### 아키텍처 분석
- `api/workflows/` (그래프 기반 워크플로)와 `api/mcp/` (도구 레지스트리·실행기)의 현황 파악
- 두 시스템이 설계되어 있으나 연결되지 않은 상태 확인
- 오케스트레이터(`orchestrator.py`)의 TODO(노드 실행 미구현) 확인

### MCP 로컬 도구 핸들러 인프라
- `api/mcp/local_tools.py` 신규 생성 — Python 함수를 MCP 도구 핸들러로 등록·조회
- `api/mcp/executor.py` 수정 — 로컬 핸들러 우선 실행, 없으면 원격 MCPClient 폴백

### 샘플 워크플로 패키지
- `api/workflows/sample/` 패키지 생성
  - `tools.py`: `greet` (인사말 생성) + `translate` (한국어↔영어 번역) 도구 등록
  - `nodes.py`: `entry_node`, `greet_node`, `translate_node` — 각 노드가 MCP 도구 호출
  - `graph.py`: `entry → greet → translate → 완료` 그래프 정의

### 오케스트레이터 실행 루프 구현
- `api/workflows/orchestrator.py`의 TODO를 `run_graph()` 함수로 교체
- 노드 실행 → `NodeResult` 수신 → 상태 갱신 → `action="resume"`이면 다음 노드 즉시 실행
- `MAX_RESUME_STEPS` (20) 안전장치로 무한 루프 방지

### 테스트
- `tests/test_sample_workflow.py` 작성 (9개 테스트)
  - 개별 도구 호출: greet, translate (ko→en, en→ko, 사전 미등록 폴백)
  - 워크플로 end-to-end: 전체 흐름 완료 확인, 노드 실행 순서 검증
  - 에러 처리: 잘못된 인자 시 `success=False` 반환
  - 통합: `handle_message()` 경유 전체 동작 확인

### 워크플로 ↔ 일반 대화 분류 논의
- `general_chat`이 프론트 도어 역할 — classify 노드에서 의도 분석 후 적절한 워크플로로 handoff
- 일반 대화는 도구 없이 LLM 직접 응답, 특정 요청(차트/PPT/번역 등)은 전용 워크플로로 진입

---

## 2. 수정 내용

### 새로 생성된 파일
| 파일 | 설명 |
|------|------|
| `api/mcp/local_tools.py` | 로컬 Python 함수 → MCP 도구 핸들러 등록/조회 |
| `api/workflows/sample/__init__.py` | 샘플 워크플로 패키지 |
| `api/workflows/sample/tools.py` | greet + translate 도구 등록 (스텁 사전 기반) |
| `api/workflows/sample/nodes.py` | entry, greet, translate 노드 (MCP 도구 호출) |
| `api/workflows/sample/graph.py` | entry → greet → translate 그래프 정의 |
| `tests/test_sample_workflow.py` | 9개 테스트 (도구, 워크플로, 통합) |

### 수정된 파일
| 파일 | 변경 내용 |
|------|----------|
| `api/mcp/executor.py` | 로컬 핸들러 우선 디스패치 로직 추가 |
| `api/workflows/orchestrator.py` | `run_graph()` 실행 루프 구현 (TODO 해소) |
| `api/workflows/registry.py` | `sample` 워크플로 등록 추가 |

---

## 3. 다음 단계

- **`general_chat` classify 노드 구현**: 사용자 메시지 의도 분석 → 일반 대화 vs 워크플로 handoff 분기
- **오케스트레이터 handoff 처리**: `action="handoff"` 시 다른 워크플로로 전환하는 로직 (`run_graph` 확장)
- **실제 번역 도구**: `_translate` 스텁을 LLM 또는 번역 API 호출로 교체
- **기존 워크플로 노드에 도구 호출 추가**: chart_maker, ppt_maker 등에 실제 MCP 도구 연결

---

## 4. 메모리 업데이트

워크플로 ↔ MCP 아키텍처 연동 패턴이 확립되었으므로 메모리 업데이트 진행.
