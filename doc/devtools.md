# Devtools 가이드

이 문서는 왜 `devtools/`가 필요한지와, 새 워크플로를 `api/workflows/`에 넣기 전에 어떤 절차로 개발해야 하는지 설명합니다.

## devtools의 목적

`devtools/`는 운영 코드와 실험 코드를 분리하기 위한 안전장치입니다.

- 새 워크플로를 운영 데이터와 섞지 않고 빠르게 검증할 수 있습니다.
- 브라우저 기반 runner로 interrupt, resume, 상태 전이를 바로 확인할 수 있습니다.
- 스캐폴딩과 promotion 스크립트로 작업 방식을 표준화할 수 있습니다.
- 팀원이 같은 구조로 워크플로를 만들 수 있어 리뷰 비용을 줄일 수 있습니다.
- 운영 경로를 직접 건드리기 전에 실패를 dev 환경에서 흡수할 수 있습니다.

즉, `devtools/`는 단순한 편의 기능이 아니라 워크플로 개발의 안전한 staging 영역 역할을 합니다.

## devtools 구성 요소

### `devtools/workflows/`

- 승격 전 워크플로 패키지를 두는 위치입니다.
- `_template/`는 새 워크플로의 기본 구조를 제공합니다.
- `translator_example/`, `travel_planner_example/`는 참고용 예제입니다.

### `devtools/mcp/`

- dev 워크플로에서 사용하는 MCP 도구 등록 코드를 두는 위치입니다.
- 운영 반영 시 같은 이름으로 `api/mcp/` 아래로 이동할 수 있습니다.

### `devtools/workflow_runner/`

- 로컬 브라우저 UI에서 워크플로를 직접 실행하는 개발용 앱입니다.
- 메시지, 현재 상태, interrupt 여부, 간단한 trace를 한 화면에서 확인할 수 있습니다.
- 운영 대화 이력 대신 `devtools/var/conversation_history/`를 사용합니다.

### `devtools/scripts/new_workflow.py`

- 새 워크플로 패키지와 dev MCP 파일을 자동 생성합니다.
- 파일 이름, 기본 함수, 기본 구조를 팀 공통 규칙에 맞춰 시작하게 도와줍니다.

### `devtools/scripts/promote.py`

- 검증이 끝난 dev 워크플로를 `api/workflows/`로 복사합니다.
- 관련 dev MCP 파일도 함께 `api/mcp/`로 옮깁니다.
- `devtools.mcp.*` import를 `api.mcp.*`로 자동 치환합니다.
- import 검증이 실패하면 자동 롤백합니다.

## 새 워크플로를 추가하는 표준 절차

### 1. devtools에서 스캐폴딩합니다

먼저 운영 디렉터리가 아니라 `devtools/`에서 시작합니다.

```bash
python -m devtools.scripts.new_workflow my_workflow
```

이 명령은 아래 항목을 생성합니다.

- `devtools/workflows/my_workflow/__init__.py`
- `devtools/workflows/my_workflow/lg_state.py`
- `devtools/workflows/my_workflow/lg_graph.py`
- `devtools/mcp/my_workflow.py`

### 2. 상태와 그래프를 구현합니다

- `lg_state.py`에서 워크플로 상태 필드를 정의합니다.
- `lg_graph.py`에서 노드와 엣지를 정의합니다.
- 필요하면 패키지 안에 `prompts.py`, `tools.py`, `nodes.py`를 추가합니다.

이때 패키지 내부 import는 반드시 상대 import를 사용합니다.

```python
from .lg_state import MyWorkflowState
from .lg_graph import build_lg_graph
```

이 규칙을 지켜야 나중에 `api/workflows/`로 옮겨도 import가 깨지지 않습니다.

### 3. dev MCP 도구를 연결합니다

외부 도구나 로컬 핸들러가 필요하면 `devtools/mcp/my_workflow.py`에 등록합니다.

- dev 단계에서는 `devtools.mcp.*`를 사용합니다.
- promotion 시 이 import는 `api.mcp.*`로 자동 치환됩니다.

### 4. dev runner에서 직접 검증합니다

```bash
python -m devtools.workflow_runner.app
```

브라우저에서 `http://localhost:5001`로 접속해 아래 항목을 확인합니다.

- 첫 메시지에서 기대한 노드가 실행되는지 확인합니다.
- interrupt가 필요한 경우 사용자 질문이 올바르게 노출되는지 확인합니다.
- 다음 메시지에서 resume이 정상 동작하는지 확인합니다.
- 상태 패널에서 슬롯 값이 기대대로 쌓이는지 확인합니다.

### 5. 테스트를 작성하고 실행합니다

- devtools 예제 수준을 넘는 실제 워크플로라면 `tests/`에 테스트를 추가하는 편이 좋습니다.
- 최소한 정상 완료 경로와 interrupt/resume 경로는 자동화하는 편이 좋습니다.

```bash
pytest tests/ -v
```

### 6. 운영 반영 전에 마지막 점검을 합니다

운영 반영 전에는 아래 항목을 확인합니다.

- `workflow_id`가 중복되지 않는지 확인합니다.
- `get_workflow_definition()`이 정확한 dict를 반환하는지 확인합니다.
- `handoff_keywords`가 너무 넓지 않은지 확인합니다.
- dev 전용 실험 코드가 남아 있지 않은지 확인합니다.

### 7. promotion으로 `api/workflows/`에 반영합니다

```bash
python -m devtools.scripts.promote my_workflow
```

이 단계에서 스크립트는 아래 작업을 수행합니다.

1. `devtools/workflows/my_workflow/`를 `api/workflows/my_workflow/`로 복사합니다.
2. 관련 `devtools/mcp/my_workflow.py`를 `api/mcp/`로 복사합니다.
3. `devtools.mcp.*` import를 `api.mcp.*`로 바꿉니다.
4. import 검증을 수행합니다.
5. 검증이 통과하면 dev 원본을 삭제합니다.

## 왜 바로 `api/workflows/`에 만들지 않는가

바로 운영 디렉터리에서 시작하면 아래 문제가 생기기 쉽습니다.

- 운영 코드와 실험 코드의 경계가 흐려집니다.
- 멀티턴 상태 오류를 브라우저에서 빠르게 확인하기 어렵습니다.
- import 구조와 MCP 연결을 반복해서 수동 정리하게 됩니다.
- 팀원마다 워크플로 구조가 달라져 리뷰 기준이 흔들립니다.

따라서 이 저장소에서는 `devtools에서 설계하고, 검증한 뒤, promote로 반영하는 흐름`을 기본 프로세스로 보는 편이 맞습니다.

## 팀 공통 권장사항

- 새 워크플로는 항상 `devtools/scripts/new_workflow.py`로 시작합니다.
- 운영 반영 전까지는 `devtools/workflow_runner/`에서 반드시 한 번 이상 대화 흐름을 확인합니다.
- dev MCP 도구는 promotion을 고려해 파일명과 `workflow_id`를 일치시키는 편이 좋습니다.
- `handoff_keywords`는 실제 사용자 발화와 충돌 가능성을 같이 검토합니다.
- 운영 반영 후에는 전체 테스트를 다시 실행합니다.

이 원칙을 따르면 워크플로 추가 속도와 운영 안정성을 함께 가져갈 수 있습니다.
