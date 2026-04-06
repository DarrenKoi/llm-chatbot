# 로컬 워크플로 개발 가이드

> Cube 없이 로컬에서 워크플로를 개발하고 검증하는 방법을 안내합니다.

---

## 빠른 시작

```bash
# 1. 새 워크플로 생성
python -m devtools.scripts.new_workflow my_workflow

# 2. 코드 작성 (아래 "워크플로 구조" 참고)

# 3. dev runner 실행
python -m devtools.workflow_runner.app

# 4. 브라우저에서 http://localhost:5001 접속 → 워크플로 선택 → 테스트
```

---

## 핵심 규칙

### 1. 상대 import 사용

워크플로 패키지 내부에서는 **반드시 상대 import**를 사용합니다.
이렇게 해야 `devtools/workflows/` → `api/workflows/`로 이동할 때 import가 깨지지 않습니다.

```python
# 같은 패키지 내 모듈 — 상대 import
from .state import MyState
from .graph import build_graph
from . import nodes

# 공유 인프라 — 절대 import OK
from api.workflows.models import NodeResult, WorkflowState
from api.mcp.executor import execute_tool_call
```

### 2. 워크플로 구조

모든 워크플로는 동일한 4파일 구조를 따릅니다:

```
devtools/workflows/my_workflow/
    __init__.py   # get_workflow_definition() 정의
    state.py      # WorkflowState를 상속한 상태 클래스
    graph.py      # build_graph() → {"nodes": {...}, "entry_node_id": "entry"}
    nodes.py      # 노드 함수들 (state, user_message) -> NodeResult
```

### 3. 노드 함수 규약

```python
def my_node(state: MyState, user_message: str) -> NodeResult:
    # action 종류:
    #   "reply"    — 응답을 보내고 멈춤
    #   "wait"     — 사용자 입력을 기다림
    #   "resume"   — 즉시 다음 노드로 이어서 실행
    #   "complete" — 워크플로 종료
    #   "handoff"  — 다른 워크플로로 전환
    return NodeResult(
        action="reply",
        reply="응답 메시지",
        next_node_id="next_node",
        data_updates={"key": "value"},
    )
```

### 4. get_workflow_definition() 필수 필드

```python
def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "my_workflow",          # 필수
        "entry_node_id": "entry",              # 필수
        "build_graph": build_graph,            # 필수 (callable)
        "state_cls": MyState,                  # 선택 (기본: WorkflowState)
        "handoff_keywords": ("키워드1",),       # 선택 (start_chat에서 handoff 트리거)
    }
```

---

## Dev Runner UI 기능

| 기능 | 설명 |
|------|------|
| **Message 패널** | 메시지 입력 + 대화 기록 (브라우저 localStorage 기반) |
| **State 패널** | 현재 워크플로 상태 JSON 실시간 표시 |
| **Trace 패널** | step별 실행 trace (노드 이름, action, 소요 시간) |
| **Reset 버튼** | 서버 state + 브라우저 대화 기록 초기화 |
| **Reload 버튼** | 워크플로 코드 변경 후 재로드 (프로세스 재시작 없이) |
| **Export JSON/TXT** | 대화 기록을 파일로 내보내기 |

---

## 주의사항

### Production 데이터와 분리

- Dev runner의 state 파일은 `devtools/var/workflow_state/`에 저장됩니다 (gitignore됨).
- 대화 기록은 브라우저 localStorage에만 저장됩니다.
- Production의 `api/workflows/` state와 대화 이력에는 영향을 주지 않습니다.

### LLM이 필요한 워크플로

- LLM을 호출하는 노드가 있다면 `.env`에 `LLM_BASE_URL`과 `LLM_API_KEY`가 설정되어 있어야 합니다.
- 규칙 기반 워크플로(travel_planner 등)는 LLM 없이 동작합니다.

### Port 설정

- 기본 port: **5001** (production 5000과 충돌 방지)
- 변경: `DEV_RUNNER_PORT=5002 python -m devtools.workflow_runner.app`

---

## Promotion (운영 반영)

워크플로 개발이 완료되면 promotion 스크립트로 `api/workflows/`로 이동합니다:

```bash
python -m devtools.scripts.promote my_workflow
```

스크립트가 수행하는 단계:
1. `devtools/workflows/my_workflow/` → `api/workflows/my_workflow/`로 복사
2. import 검증 (실패 시 자동 롤백)
3. 검증 통과 후 dev 소스 삭제
4. dev state 파일 정리

Promotion 후:
1. `pytest tests/ -v`로 전체 테스트 실행
2. `git add api/workflows/my_workflow/`로 스테이징
3. 코드 리뷰 → 배포

---

## 자주 하는 실수

| 실수 | 해결 |
|------|------|
| `from devtools.workflows.my_wf.state import ...` | 상대 import 사용: `from .state import ...` |
| Reload 눌러도 코드 변경이 안 반영됨 | Flask debug 모드에서 파일 저장 시 자동 재시작됨. Reload는 새 워크플로 추가 시 사용 |
| state가 이상해짐 | Reset 버튼으로 초기화 |
| `get_workflow_definition()` 없음 오류 | `__init__.py`에 함수를 정의했는지 확인 |
| `_` prefix 워크플로가 안 보임 | `_`로 시작하는 패키지는 registry가 자동 스킵합니다 (예: `_template`) |
