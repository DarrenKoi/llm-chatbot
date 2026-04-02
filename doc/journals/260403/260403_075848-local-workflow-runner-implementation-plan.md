# Local Workflow Runner 구현 계획서

> 이전 세션(`260403_073549`)에서 정리한 아키텍처 방향을 기반으로, 코드베이스를 정밀 분석하여 작성한 구현 계획이다.
> 프로젝트가 충분히 성숙한 시점에 실행한다.

---

## 1. 배경과 목적

현재 workflow 개발은 `api/workflows/` 안에서 직접 이루어지며, 실행과 테스트는 Cube 플랫폼(Redis 큐, 메시지 워커)을 거쳐야 한다. 집에서 코딩하고 사무실에서 테스트하는 환경 특성상, Cube 없이 localhost에서 workflow를 개발/검증할 수 있는 독립 환경이 필요하다. 완성된 workflow를 `api/workflows/`로 폴더째 옮기면 바로 동작하는 seamless promotion이 핵심 요구사항이다.

---

## 2. Import 규칙 전환 (가장 중요한 결정)

### 현재 상태

모든 기존 workflow가 절대 import를 사용한다.

```python
# travel_planner/__init__.py
from api.workflows.travel_planner.graph import build_graph

# travel_planner/nodes.py
from api.workflows.travel_planner.state import TravelPlannerState

# travel_planner/graph.py
from api.workflows.travel_planner import nodes
```

### 문제

`devtools/workflows/`에서 개발하면 `devtools.workflows.my_workflow.X`로 import해야 하고, promotion 시 `api.workflows.my_workflow.X`로 전부 바꿔야 한다. "폴더만 옮기면 끝" 이 안 된다.

### 해결: 상대 import 규칙

새 workflow는 **상대 import**를 사용한다.

```python
# __init__.py
from .graph import build_graph      # 어디서든 동작
from .state import MyState          # 어디서든 동작

# nodes.py
from .state import MyState          # 상대 import
from api.workflows.models import NodeResult  # 공유 인프라는 절대 import OK

# graph.py
from . import nodes                 # 상대 import
```

이렇게 하면 폴더를 `devtools/workflows/` → `api/workflows/`로 이동해도 import가 깨지지 않는다. 기존 production workflow는 변경하지 않는다.

**import 규칙 요약**:

| 대상 | 방식 | 예시 |
|---|---|---|
| 같은 workflow 패키지 내 모듈 | 상대 import | `from .state import MyState` |
| 공유 인프라 (`api.workflows.models` 등) | 절대 import | `from api.workflows.models import NodeResult` |
| 외부 서비스 (`api.llm`, `api.mcp` 등) | 절대 import | `from api.mcp.executor import execute_tool_call` |

---

## 3. 디렉토리 구조

```
devtools/
    __init__.py                          # 빈 파일 (패키지화)
    workflows/
        __init__.py                      # 빈 파일 (패키지화)
        _template/                       # starter template (_ prefix → registry가 스킵)
            __init__.py
            state.py
            graph.py
            nodes.py
    workflow_runner/
        __init__.py
        app.py                           # Flask dev 서버 (port 5001)
        routes.py                        # API 엔드포인트
        dev_orchestrator.py              # run_graph 래퍼 (trace 수집)
        templates/
            runner.html                  # 단일 페이지 dev UI
        static/
            runner.js                    # fetch API + localStorage transcript
            runner.css                   # 스타일
    var/
        workflow_state/                  # dev 전용 상태 디렉토리 (gitignore)
    scripts/
        promote.py                       # devtools → api 이동 스크립트
        new_workflow.py                  # template 기반 scaffold
```

---

## 4. 기존 인프라 재활용 포인트

Production 코드를 수정하지 않고, 기존 인프라를 그대로 가져다 쓴다.

### 4-1. Registry (`api/workflows/registry.py`)

`discover_workflows()` 함수가 이미 `package_name` 파라미터를 지원한다 (line 22).

```python
# dev runner에서 호출
discover_workflows(package_name="devtools.workflows")
```

`_` prefix 스킵 규칙(line 38: `short_name.startswith("_")`)으로 `_template/`은 자동 제외된다.

**주의**: `load_workflows()`의 글로벌 `_WORKFLOWS` 캐시에 dev workflow가 섞이면 안 된다. Dev runner에서는 `discover_workflows()`를 직접 호출하고, `load_workflows()`는 사용하지 않는다.

### 4-2. State Service (`api/workflows/state_service.py`)

`WORKFLOW_STATE_DIR` env var로 경로를 제어할 수 있다 (`config.py` line 80).

```python
# dev runner의 app.py에서 api.* import 전에 설정
os.environ.setdefault(
    "WORKFLOW_STATE_DIR",
    str(Path(__file__).resolve().parent.parent / "var" / "workflow_state")
)
```

`load_state()`, `save_state()`, `clear_state()` 함수를 그대로 사용한다.

**주의**: `state_service.get_state_class()`가 내부적으로 `get_workflow()` → `load_workflows()`를 호출한다. Dev workflow는 여기에 등록되지 않으므로, dev orchestrator에서 `register_state_class(workflow_id, cls)`를 명시적으로 호출해야 한다.

### 4-3. Models (`api/workflows/models.py`)

`WorkflowState`, `NodeResult` 등 핵심 데이터 클래스를 그대로 사용한다. 위치에 무관하게 `from api.workflows.models import ...`로 접근한다.

### 4-4. Conversation Service 비사용

Production에서는 `cube/service.py`가 `conversation_service.append_message()`를 호출하지만, dev runner는 이를 호출하지 않는다. Transcript는 브라우저 localStorage에서만 관리한다. LLM을 쓰는 workflow에서 대화 이력이 필요하면 dev orchestrator가 request에서 받은 transcript를 직접 주입한다.

---

## 5. 구현 단계

### Step 1: Package Skeleton

`devtools/__init__.py`, `devtools/workflows/__init__.py` — 빈 `__init__.py`로 Python 패키지 구성.

### Step 2: Workflow Template

`devtools/workflows/_template/` 하위 4개 파일. 상대 import 규칙을 적용한 boilerplate:

- `__init__.py`: `from .graph import build_graph`, `from .state import ...`
- `state.py`: `from api.workflows.models import WorkflowState`
- `graph.py`: `from . import nodes`
- `nodes.py`: `from api.workflows.models import NodeResult`, `from .state import ...`

### Step 3: Dev Orchestrator

`devtools/workflow_runner/dev_orchestrator.py`

`api/workflows/orchestrator.py`의 `run_graph()` (line 142-186, 약 45줄)를 복제하되, 각 노드 실행마다 trace 데이터를 수집하는 버전을 만든다.

```python
def run_graph_with_trace(graph, state, user_message) -> tuple[str, list[dict]]:
    """run_graph와 동일한 실행 루프 + step별 trace 수집."""
```

trace 항목:

| 필드 | 타입 | 설명 |
|---|---|---|
| `step` | int | step 카운터 |
| `node_id` | str | 실행된 노드 |
| `workflow_id` | str | 현재 workflow |
| `action` | str | NodeResult action |
| `reply_preview` | str | reply 앞 100자 |
| `next_node_id` | str/null | 다음 노드 |
| `data_updates` | dict | 변경된 data 키 목록 |
| `elapsed_ms` | int | 소요 시간 (ms) |
| `state_snapshot` | dict | step 후 state 직렬화 |

Production `run_graph()`는 수정하지 않는다. Dev 버전은 동일 루프에 `time.perf_counter()` 계측과 snapshot 수집만 추가한다.

### Step 4: Flask Dev App

`devtools/workflow_runner/app.py`

- `WORKFLOW_STATE_DIR` env var를 import 전에 설정
- Flask app factory, port 5001 (production 5000과 충돌 방지)
- 프로젝트 루트를 `sys.path`에 추가

### Step 5: API Routes

`devtools/workflow_runner/routes.py`

| Endpoint | Method | 역할 |
|---|---|---|
| `/` | GET | runner.html 서빙 |
| `/api/workflows` | GET | dev workflow 목록 반환 |
| `/api/send` | POST | 메시지 전송 → reply + trace + state 반환 |
| `/api/state` | GET | 현재 workflow state 조회 |
| `/api/state` | DELETE | state 초기화 (reset) |

`/api/send` 응답 형식:

```json
{
    "reply": "도쿄 3박 4일 여행은...",
    "state": {
        "user_id": "dev_user",
        "workflow_id": "travel_planner",
        "node_id": "build_plan",
        "status": "waiting_user_input",
        "data": { "destination": "도쿄", "duration_text": "3박4일" }
    },
    "trace": [
        { "step": 0, "node_id": "entry", "action": "resume", "elapsed_ms": 2 },
        { "step": 1, "node_id": "collect_info", "action": "wait", "elapsed_ms": 5 }
    ]
}
```

### Step 6: Dev UI

`runner.html`, `runner.js`, `runner.css` — 단일 페이지, 4개 패널:

1. **Message Panel**: 입력창 + 대화 이력 (localStorage 기반)
2. **State Panel**: workflow state JSON 뷰어 (실시간)
3. **Trace Panel**: step-by-step 실행 trace 타임라인
4. **Controls Bar**: workflow 선택 드롭다운, Reset 버튼, Export 드롭다운 (JSON/TXT)

기존 프로젝트 UI 스타일(Jinja2 template, 빌드 도구 없음)과 동일한 패턴을 따른다.

### Step 7: Scaffold Script

`devtools/scripts/new_workflow.py`

```bash
python devtools/scripts/new_workflow.py my_new_workflow
```

- `_template/`를 `devtools/workflows/my_new_workflow/`로 복사
- placeholder(`__WORKFLOW_ID__`, `__STATE_CLASS__`)를 실제 값으로 치환
- 다음 단계 안내 출력

### Step 8: Promotion Script

`devtools/scripts/promote.py`

```bash
python devtools/scripts/promote.py my_new_workflow
```

1. `devtools/workflows/my_new_workflow/` 존재 확인
2. `api/workflows/my_new_workflow/` 미존재 확인 (충돌 방지)
3. Safety net: `.py` 파일에서 `devtools.workflows.my_new_workflow` 문자열 검색 → 있으면 `api.workflows.my_new_workflow`로 치환 (상대 import 규칙을 따랐다면 변경 없음)
4. `shutil.move()`로 이동
5. Import validation: `api.workflows.my_new_workflow`를 import하고 `get_workflow_definition()` 호출하여 로드 검증
6. Dev state 파일 정리
7. `pytest` 실행 안내 출력

### Step 9: Gitignore 업데이트

`.gitignore`에 추가:

```
var/
devtools/var/
```

---

## 6. Config Override 타이밍

`api/config.py`는 import 시점에 `.env`를 읽는다 (line 9-12). Dev runner의 `app.py`에서 `api.*` import 전에 `os.environ`을 설정해야 override가 적용된다.

```python
# devtools/workflow_runner/app.py 최상단
import os
from pathlib import Path

os.environ.setdefault(
    "WORKFLOW_STATE_DIR",
    str(Path(__file__).resolve().parent.parent / "var" / "workflow_state"),
)

# 이 아래에서 api.* import
from api.workflows.registry import discover_workflows
from api.workflows.state_service import load_state, save_state, clear_state
```

---

## 7. 잠재적 이슈와 대응

| 이슈 | 위험도 | 대응 |
|---|---|---|
| LLM 호출이 필요한 workflow는 네트워크 필요 | 중 | `.env`에 `LLM_BASE_URL` 설정 필수. 규칙 기반 workflow(travel_planner 등)는 LLM 없이 동작 |
| MCP tool 등록 타이밍 | 중 | `build_graph()` 호출 시 tool 등록이 트리거됨 (translator/graph.py 패턴). Dev runner에서도 동일 |
| Registry 캐시 혼합 | 중 | `discover_workflows()` 직접 호출, `load_workflows()` 사용 금지 |
| `state_service.get_state_class()` fallback | 중 | Dev orchestrator에서 `register_state_class()` 명시 호출 |
| 기존 workflow를 dev에서 테스트하고 싶을 때 | 낮 | 기존 workflow는 절대 import → devtools에서 바로 불가. 상대 import 전환 필요 또는 `api/workflows/` 그대로 테스트 |
| `api.config` side effect | 낮 | env var를 import 전에 설정 (위 섹션 참고) |
| Port 충돌 | 낮 | Dev runner는 5001 사용. env var로 변경 가능 |

---

## 8. 검증 계획

1. `python devtools/scripts/new_workflow.py sample_flow` → 디렉토리 생성 확인
2. `discover_workflows(package_name="devtools.workflows")` → `sample_flow` 포함 확인
3. `python devtools/workflow_runner/app.py` → localhost:5001 접속
4. `/api/send`로 메시지 전송 → reply, state, trace 응답 확인
5. State 파일이 `devtools/var/workflow_state/`에 저장되는지 확인 (`var/workflow_state/`가 아님)
6. Reset → state 파일 삭제 확인
7. Export → JSON/TXT 다운로드 확인
8. `python devtools/scripts/promote.py sample_flow` → `api/workflows/sample_flow/`로 이동, import 검증 통과
9. `pytest tests/` 전체 통과 확인

---

## 9. 생성할 파일 목록

### 새 파일 (15개)

| # | 파일 | 역할 |
|---|---|---|
| 1 | `devtools/__init__.py` | 패키지 init |
| 2 | `devtools/workflows/__init__.py` | 패키지 init |
| 3 | `devtools/workflows/_template/__init__.py` | workflow 정의 boilerplate |
| 4 | `devtools/workflows/_template/state.py` | state 클래스 boilerplate |
| 5 | `devtools/workflows/_template/graph.py` | 그래프 빌더 boilerplate |
| 6 | `devtools/workflows/_template/nodes.py` | 노드 함수 boilerplate |
| 7 | `devtools/workflow_runner/__init__.py` | 패키지 init |
| 8 | `devtools/workflow_runner/app.py` | Flask dev 서버 |
| 9 | `devtools/workflow_runner/routes.py` | API 엔드포인트 |
| 10 | `devtools/workflow_runner/dev_orchestrator.py` | trace 수집 orchestrator |
| 11 | `devtools/workflow_runner/templates/runner.html` | dev UI 페이지 |
| 12 | `devtools/workflow_runner/static/runner.js` | 클라이언트 JS |
| 13 | `devtools/workflow_runner/static/runner.css` | 스타일시트 |
| 14 | `devtools/scripts/new_workflow.py` | scaffold 스크립트 |
| 15 | `devtools/scripts/promote.py` | promotion 스크립트 |

### 수정할 파일 (1개)

| # | 파일 | 변경 내용 |
|---|---|---|
| 1 | `.gitignore` | `var/`, `devtools/var/` 추가 |

---

## 10. 핵심 참조 파일

구현 시 반드시 확인해야 할 파일들:

- `api/workflows/orchestrator.py` — `run_graph()` (line 142-186): dev orchestrator가 복제할 대상
- `api/workflows/registry.py` — `discover_workflows()` (line 21-51): dev workflow 탐색 hook
- `api/workflows/state_service.py` — state 저장/로드 함수: dev runner가 그대로 사용
- `api/workflows/models.py` — `WorkflowState`, `NodeResult`: 모든 workflow의 기반 클래스
- `api/config.py` — `WORKFLOW_STATE_DIR` (line 80): env var override 대상
- `api/workflows/travel_planner/` — 참조 구현 (LLM 없이 동작하는 규칙 기반 workflow)
