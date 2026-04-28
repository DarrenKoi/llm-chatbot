# 로컬 워크플로 개발 가이드

> Cube 없이 로컬에서 워크플로를 개발하고 검증하는 방법을 안내합니다.

---

## 빠른 시작

```bash
# 1. 새 워크플로 생성
python -m devtools.scripts.new_workflow my_workflow

# 2. 예제 참고 후 코드 작성
#    - devtools/workflows/_template/
#    - devtools/workflows/travel_planner_example/
#    - devtools/mcp_runtime/<workflow_id>.py

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
from .lg_state import MyState
from .lg_graph import build_lg_graph

# 공유 인프라 — 절대 import OK
from api.workflows.lg_state import ChatState
from api.mcp_runtime.executor import execute_tool_call

# dev 전용 MCP helper — promotion 시 api.mcp_runtime.* 로 자동 치환
from devtools.mcp_runtime.my_workflow import register_tools
```

### 2. 워크플로 구조

최소 구조는 아래 3파일입니다:

```
devtools/workflows/my_workflow/
    __init__.py   # get_workflow_definition() 정의
    lg_state.py   # ChatState 확장 TypedDict
    lg_graph.py   # build_lg_graph() -> StateGraph
```

워크플로에서 사용하는 MCP helper를 분리하고 싶다면
같은 이름의 모듈이나 패키지를 `devtools/mcp_runtime/` 아래에 둡니다:

```
devtools/mcp_runtime/my_workflow.py
```

또는

```
devtools/mcp_runtime/my_workflow/
    __init__.py
```

실제 운영 워크플로와 비슷하게 만들려면 필요에 따라 아래 파일도 추가합니다:

```
devtools/workflows/my_workflow/
    prompts.py    # 프롬프트 상수
    tools.py      # MCP/local tool 등록
```

참고 예제:

- `devtools/workflows/_template/`
- `devtools/workflows/travel_planner_example/`

위 예제는 기본 패키지 구조와 멀티턴 interrupt/resume를 보여주는 샘플입니다. devtools 워크플로는 Cube에 직접 보내지 않고 평문 LLM 응답까지만 만드는 것이 원칙입니다 (richnotification·multimessage·rich block은 운영 `api/cube/`의 책임).
scaffold로 생성한 기본 `lg_graph.py`는 같은 이름의 `devtools.mcp_runtime/<workflow_id>.py`
의 `register_tools()`를 바로 호출합니다.

필요하면 예제처럼 워크플로 내부 `tools.py`를 유지해도 되지만,
워크플로와 MCP helper를 분리하고 싶을 때는 `devtools/mcp_runtime/`를 사용합니다.

### 3. LangGraph 노드 규약

```python
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt


def collect_slot_node(state: MyState) -> dict:
    user_input = interrupt({"reply": "누락된 정보를 입력해주세요."})
    return {"user_message": user_input}


def complete_node(state: MyState) -> dict:
    return {"messages": [AIMessage(content="완료되었습니다.")]}
```

### 4. get_workflow_definition() 필수 필드

```python
def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "my_workflow",          # 필수
        "build_lg_graph": build_lg_graph,      # 필수 (callable)
        "handoff_keywords": ("키워드1",),       # 선택 (start_chat에서 handoff 트리거)
    }
```

---

## 추천 작성 순서

1. 기본 구조는 `_template`, 멀티턴 흐름은 `travel_planner_example` 중 가까운 예제를 고릅니다. (Cube 페이로드 외형 점검은 워크플로가 아니라 `devtools/cube_message/` 도구로 합니다.)
2. 새 폴더를 만든 뒤 예제의 파일 분리 방식을 그대로 가져갑니다.
3. 패키지 내부 import는 상대 import로 유지합니다.
4. dev MCP helper가 필요하면 `devtools/mcp_runtime/<workflow_id>.py`에서 함께 정리합니다.
5. dev runner에서 먼저 검증합니다.
6. 실제 운영 연결은 `api/workflows/start_chat/`에서 handoff 기준으로 붙입니다.

## 응답 규칙

devtools에서 작업하거나 검증했다면, LLM 응답에 그 사실을 분명하게 적습니다.

- `This is done via devtools.`처럼 바로 드러나는 문장을 포함합니다.
- 변경 설명에는 해당 `devtools/...` 경로를 함께 적습니다.
- devtools 예제나 프로토타입이면 production 반영이 끝난 것처럼 말하지 않습니다.

## Dev Runner UI 기능

| 기능 | 설명 |
|------|------|
| **Message 패널** | 메시지 입력 + 대화 기록 (브라우저 localStorage 기반) |
| **State 패널** | 현재 LangGraph snapshot(JSON) 실시간 표시 |
| **Trace 패널** | 최근 실행 결과 요약 (workflow/action/소요 시간) |
| **Reset 버튼** | 서버 state + 브라우저 대화 기록 초기화 |
| **Reload 버튼** | 워크플로 코드 변경 후 재로드 (프로세스 재시작 없이) |
| **Export JSON/TXT** | 대화 기록을 파일로 내보내기 |

---

## 주의사항

### Production 데이터와 분리

- 서버 측 대화 이력은 `devtools/var/conversation_history/` 로컬 파일에 저장됩니다.
- 브라우저 transcript는 계속 localStorage에 저장됩니다.
- 기본 `user_id`는 `dev_{PC_ID}` 형식이며 `DEV_RUNNER_PC_ID` 또는 로컬 hostname 기반으로 정해집니다.
- LangGraph 상태는 dev runner 프로세스 메모리 안에서만 유지되며, Reset 또는 Reload 시 새 thread로 초기화됩니다.
- Production의 `api/workflows/` state와 대화 이력에는 영향을 주지 않습니다.

### LLM이 필요한 워크플로

- LLM을 호출하는 노드가 있다면 `.env`에 `LLM_BASE_URL`과 `LLM_API_KEY`가 설정되어 있어야 합니다.
- 규칙 기반 devtools 예제(`travel_planner_example` 등)는 LLM 없이 동작합니다.

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
2. 같은 이름의 `devtools/mcp_runtime/my_workflow.py` 또는 `devtools/mcp_runtime/my_workflow/`가 있으면 `api/mcp_runtime/`로 함께 복사
3. 복사된 코드의 `devtools.mcp_runtime.*` import를 `api.mcp_runtime.*`로 자동 치환
4. import 검증 (실패 시 자동 롤백)
5. 검증 통과 후 dev 소스 삭제

Promotion 후:
1. `pytest tests/ -v`로 전체 테스트 실행
2. `git add api/workflows/my_workflow/ api/mcp_runtime/my_workflow*`로 스테이징
3. 코드 리뷰 → 배포

---

## 자주 하는 실수

| 실수 | 해결 |
|------|------|
| `from devtools.workflows.my_wf.state import ...` | 상대 import 사용: `from .lg_state import ...` |
| `devtools.mcp_runtime.*` import를 수동으로 바꿔야 하나요? | promotion 스크립트가 `api.mcp_runtime.*`로 자동 치환합니다 |
| Reload 눌러도 코드 변경이 안 반영됨 | Flask debug 모드에서 파일 저장 시 자동 재시작됨. Reload는 새 워크플로 추가 시 사용 |
| state가 이상해짐 | Reset 버튼으로 초기화 |
| `get_workflow_definition()` 없음 오류 | `__init__.py`에 함수를 정의했는지 확인 |
| `_` prefix 워크플로가 안 보임 | `_`로 시작하는 패키지는 registry가 자동 스킵합니다 (예: `_template`) |
