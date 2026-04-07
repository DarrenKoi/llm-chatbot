# LangGraph Phase 3: start_chat + lg_orchestrator 서브그래프 구현

## 1. 진행 사항

### Phase 3 구현 완료
- **start_chat LangGraph 그래프 생성** — 자식 워크플로를 서브그래프로 포함하는 메인 StateGraph 구현
- **LangGraph 오케스트레이터 생성** — 기존 `orchestrator.py`를 대체하는 `lg_orchestrator.py` 구현
- **환경 변수 토글 추가** — `USE_LANGGRAPH` 플래그로 기존/신규 오케스트레이터 전환
- **cube/service.py 연동** — 토글에 따라 오케스트레이터 import를 동적으로 전환
- **translator handoff_keywords 추가** — 서브그래프 라우팅에 필수적인 키워드 누락 수정
- **테스트 8개 작성 및 전체 164개 통과 확인**

### 아키텍처
```
start_chat StateGraph
  ├─ entry_node (프로필 로딩)
  ├─ classify_node → 조건부 라우팅
  │   ├─ "start_chat" → retrieve_context → plan_response → generate_reply → END
  │   ├─ "translator" → translator 서브그래프 → END
  │   ├─ "chart_maker" → chart_maker 서브그래프 → END
  │   └─ "travel_planner" → travel_planner 서브그래프 → END
  └─ checkpointer로 컴파일
```

## 2. 수정 내용

### 새 파일
| 파일 | 설명 |
|------|------|
| `api/workflows/start_chat/lg_graph.py` | start_chat LangGraph StateGraph (서브그래프 포함) |
| `api/workflows/lg_orchestrator.py` | LangGraph 기반 워크플로 오케스트레이터 (`handle_message → WorkflowReply`) |
| `tests/test_start_chat_lg_graph.py` | start_chat LG 그래프 테스트 5개 (casual, translator, travel_planner 멀티턴, chart_maker) |
| `tests/test_lg_orchestrator.py` | LG 오케스트레이터 테스트 3개 (casual, translator interrupt/resume, travel_planner) |

### 수정 파일
| 파일 | 변경 내용 |
|------|----------|
| `api/config.py` | `USE_LANGGRAPH` 환경 변수 토글 추가 (L91) |
| `api/cube/service.py` | `USE_LANGGRAPH` 토글에 따라 old/new 오케스트레이터 전환 (L15-18) |
| `api/workflows/translator/__init__.py` | `handoff_keywords` 추가: `("translate", "translation", "번역", "통역")` |

### 주요 설계 결정
- **서브그래프 패턴**: 자식 워크플로의 `interrupt()`가 부모 그래프로 전파되고, `Command(resume=...)` 가 다시 자식으로 흘러감
- **handoff 스택 불필요**: LangGraph 체크포인터가 interrupt 지점을 추적하므로 기존 스택 관리 제거
- **`generate_reply_node`**: 현재는 `get_history()`로 MongoDB에서 대화 이력을 가져옴 (Phase 4에서 `messages` 상태로 이관 예정)
- **`detected_intent`**: 상태의 `detected_intent` 값이 응답의 `workflow_id`로 사용됨

### 발견 및 수정한 이슈
- **translator handoff_keywords 누락**: 기존 translator 워크플로에 `handoff_keywords`가 없어 start_chat에서 서브그래프로 라우팅 불가. 서브그래프 아키텍처에서는 모든 자식 워크플로가 `classify_node`의 키워드 매칭으로 도달하므로 키워드 추가 필수
- **mock 대상 오류**: `load_user_profile`은 `entry_node` 내부에서 lazy import하므로 `api.profile.service.load_user_profile`에서 mock해야 함 (`api.workflows.start_chat.lg_graph.load_user_profile`이 아님)

## 3. 다음 단계

### Phase 4: 클린업 (마이그레이션 계획 최종 단계)
- `api/workflows/orchestrator.py` 삭제 (lg_orchestrator로 대체)
- `api/workflows/state_service.py` 삭제 (체크포인터로 대체)
- 각 워크플로의 `lg_adapter.py` 삭제 (더 이상 불필요)
- 각 워크플로의 기존 `graph.py` 삭제 (`lg_graph.py`로 대체)
- `routing.py` 파일들 삭제 (LangGraph 조건부 엣지로 대체)
- `lg_orchestrator.py` → `orchestrator.py`, `lg_graph.py` → `graph.py` 리네이밍
- `USE_LANGGRAPH*` 토글 환경 변수 제거
- `models.py`에서 `NodeResult`, `NodeAction` 제거
- `var/workflow_state/` 디렉토리 삭제

### 미커밋 상태
- Phase 0 ~ Phase 3 변경 사항이 아직 커밋되지 않음
- 커밋 시점은 사용자 결정에 따름

## 4. 메모리 업데이트

LangGraph 마이그레이션 Phase 3 완료로 아키텍처 변경이 있으므로 메모리 업데이트 필요.
