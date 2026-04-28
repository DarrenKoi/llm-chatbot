# Devtools 가이드

> 최종 업데이트: 2026-04-28

이 문서는 `shared_docs/`에서 팀원이 공통으로 참고할 수 있도록, 현재 `devtools/`의 역할과 워크플로 개발 절차를 요약한 문서입니다.
원문 기준은 `doc/guideline/workflow_추가_가이드.md`, `doc/guideline/workflow_등록_가이드.md`, `doc/project_structure.md`입니다.

> ⚠️ **최근 변경 (2026-04-28)** — dev MCP 경로가 `devtools/mcp/` → `devtools/mcp_runtime/` 로, 운영 MCP 경로가 `api/mcp/` → `api/mcp_runtime/` 로 변경되었습니다. 호환성 shim은 제거되었으므로 `devtools.mcp.*` / `api.mcp.*` import는 더 이상 동작하지 않습니다. 본 문서의 모든 명령과 경로 예시는 새 패키지명 기준입니다.

## 1. devtools의 목적

`devtools/`는 운영 코드와 실험 코드를 분리하기 위한 안전한 staging 영역입니다.

- 새 워크플로를 운영 데이터와 섞지 않고 빠르게 검증할 수 있습니다.
- 브라우저 기반 runner로 interrupt, resume, 상태 전이를 바로 확인할 수 있습니다.
- 스캐폴딩과 promotion 스크립트로 작업 방식을 표준화할 수 있습니다.
- 팀원이 같은 구조로 워크플로를 만들 수 있어 리뷰 비용을 줄일 수 있습니다.
- 운영 경로를 직접 건드리기 전에 실패를 dev 환경에서 흡수할 수 있습니다.

즉, `devtools/`는 단순 편의 기능이 아니라 워크플로 개발의 사전 검증 계층입니다.

## 2. 현재 구성 요소

### `devtools/workflows/`

- 승격 전 워크플로 패키지를 두는 위치입니다.
- `_template/`는 새 워크플로의 기본 구조를 제공합니다.
- `travel_planner_example/`는 멀티턴 interrupt/resume 참고 예제입니다.
- `richinotification_test/`는 richnotification payload 조립과 devtools 응답 규칙 참고 예제입니다.

### `devtools/mcp_runtime/`

- dev 워크플로에서 사용하는 MCP 등록 코드를 둡니다.
- 템플릿 파일 `_template.py`를 기준으로 새 dev MCP 모듈을 생성합니다.
- promotion 시 같은 이름으로 `api/mcp_runtime/` 아래로 이동할 수 있습니다.

### `devtools/workflow_runner/`

- 로컬 브라우저 UI에서 워크플로를 직접 실행하는 개발용 앱입니다.
- 메시지, 현재 상태, interrupt 여부, 간단한 trace를 한 화면에서 확인할 수 있습니다.
- 운영용 `api/workflows/`가 아니라 `devtools/workflows/`를 자동 발견해 실행합니다.
- 대화 이력은 `devtools/var/conversation_history/`를 사용합니다.
- 상태 저장은 `devtools/var/workflow_state/`를 사용합니다.

### `devtools/scripts/new_workflow.py`

- 새 워크플로 패키지와 dev MCP 파일을 자동 생성합니다.
- `workflow_id` 형식은 `^[a-z][a-z0-9_]*$` 규칙으로 검증합니다.
- 템플릿 복사 후 `__WORKFLOW_ID__`, 상태 클래스명 등을 치환합니다.

### `devtools/scripts/promote.py`

- 검증이 끝난 dev 워크플로를 `api/workflows/`로 승격합니다.
- 관련 dev MCP 파일도 함께 `api/mcp_runtime/`로 복사합니다.
- `devtools.mcp_runtime.*` import를 `api.mcp_runtime.*`로 자동 치환합니다.
- import 검증이 실패하면 롤백합니다.
- 검증 통과 후 dev 원본을 삭제합니다.

## 3. 새 워크플로를 추가하는 표준 절차

### 1. `workflow_id`를 먼저 정합니다

`workflow_id`는 아래 항목의 기준점이 됩니다.

- dev 워크플로 디렉터리명
- 레지스트리 식별자
- handoff 대상 이름
- dev MCP 파일명
- 운영 MCP 파일명

처음부터 소문자 `snake_case`로 정하고, 업무 단위가 드러나는 이름을 쓰는 편이 좋습니다.

### 2. devtools에서 스캐폴딩합니다

```bash
python -m devtools.scripts.new_workflow my_workflow
```

이 명령은 아래 항목을 생성합니다.

- `devtools/workflows/my_workflow/__init__.py`
- `devtools/workflows/my_workflow/lg_state.py`
- `devtools/workflows/my_workflow/lg_graph.py`
- `devtools/mcp_runtime/my_workflow.py`

현재 템플릿은 `lg_state.py`를 기본 상태 파일로 사용합니다.
오래된 문서처럼 `state.py`를 만드는 구조가 아닙니다.

### 3. 상태와 그래프를 구현합니다

- `lg_state.py`에서 워크플로 상태 필드를 정의합니다.
- `lg_graph.py`에서 노드와 엣지를 정의합니다.
- 필요하면 패키지 안에 `prompts.py`, `tools.py`, `nodes.py`를 추가합니다.

상태 설계 원칙:

- 공통 기본 상태는 `api/workflows/lg_state.py`의 `ChatState`를 상속합니다 (legacy — 격리 정책에 따라 `devtools/` 자체 mirror로 이전 예정, 자세한 내용은 [`workflow_catalog.md`](./workflow_catalog.md) §3.5 참조).
- 워크플로 전용 슬롯만 각 패키지의 `lg_state.py`에 둡니다.
- `total=False`를 유지해 선택 필드를 자연스럽게 비울 수 있게 합니다.

### 4. import 규칙을 지킵니다

현재 구조에서 패키지 내부 import는 상대 import를 쓰는 편이 안전합니다.

좋은 예:

```python
from .lg_state import MyWorkflowState
from .lg_graph import build_lg_graph
```

반면 MCP 모듈은 promotion에서 `devtools.mcp_runtime.`를 `api.mcp_runtime.`로 치환하므로, 템플릿처럼 `devtools.mcp_runtime.<workflow_id>` 형태를 사용할 수 있습니다.

주의할 점:

- 자기 워크플로 패키지를 `devtools.workflows.<workflow_id>`로 절대 import하면 promotion 경고 대상이 됩니다.
- `promote.py`는 이런 절대 import 잔존 여부를 검사합니다.

### 5. dev MCP 도구를 연결합니다

외부 도구나 로컬 핸들러가 필요하면 `devtools/mcp_runtime/my_workflow.py`에 등록합니다.

- dev 단계에서는 `devtools.mcp_runtime.*`를 사용합니다.
- promotion 시 이 prefix는 `api.mcp_runtime.*`로 바뀝니다.
- 도구가 필요한 워크플로는 `build_lg_graph()` 경로에서 등록 함수를 호출해야 합니다.

### 6. dev runner에서 직접 검증합니다

```bash
python -m devtools.workflow_runner.app
```

브라우저에서 아래 항목을 확인합니다.

- 첫 메시지에서 기대한 노드가 실행되는지 확인합니다.
- interrupt가 필요한 경우 질문이 올바르게 노출되는지 확인합니다.
- 다음 메시지에서 resume이 정상 동작하는지 확인합니다.
- 상태 패널에서 슬롯 값이 기대대로 쌓이는지 확인합니다.

### 7. 테스트를 작성하고 실행합니다

실제 워크플로라면 `tests/`에 테스트를 추가하는 편이 좋습니다.

최소 권장 검증:

- 정상 완료 경로
- interrupt 경로
- resume 경로
- registry 발견
- `start_chat` handoff

```bash
pytest tests/ -v
```

### 8. promotion으로 운영 반영합니다

```bash
python -m devtools.scripts.promote my_workflow
```

이 단계에서 스크립트는 아래 작업을 수행합니다.

1. `devtools/workflows/my_workflow/`를 `api/workflows/my_workflow/`로 복사합니다.
2. 관련 `devtools/mcp_runtime/my_workflow.py`를 `api/mcp_runtime/`로 복사합니다.
3. `devtools.mcp_runtime.*` import를 `api.mcp_runtime.*`로 바꿉니다.
4. import 검증을 수행합니다.
5. 검증이 통과하면 dev 원본을 삭제합니다.

## 4. 왜 바로 `api/workflows/`에 만들지 않는가

바로 운영 디렉터리에서 시작하면 아래 문제가 생기기 쉽습니다.

- 운영 코드와 실험 코드의 경계가 흐려집니다.
- 멀티턴 상태 오류를 브라우저에서 빠르게 확인하기 어렵습니다.
- import 구조와 MCP 연결을 반복해서 수동 정리하게 됩니다.
- 팀원마다 워크플로 구조가 달라져 리뷰 기준이 흔들립니다.

따라서 이 저장소에서는 “devtools에서 설계하고 검증한 뒤, promote로 운영 반영한다”는 흐름을 기본 프로세스로 보는 편이 맞습니다.

## 5. 등록과 handoff 관점에서 기억할 점

devtools도 운영과 같은 자동 발견 메커니즘을 따릅니다.

- `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`이 있어야 합니다.
- `build_lg_graph`는 callable이어야 합니다.
- `handoff_keywords`가 비어 있으면 등록은 되더라도 자동 handoff 대상은 아닙니다.
- 키워드는 실제 사용자 발화 기준으로 좁고 분명하게 설계해야 합니다.

즉, dev 단계에서도 “패키지 계약을 맞춰 자동 발견 구조에 태운다”는 개념이 동일하게 적용됩니다.

## 6. 팀 공통 권장사항

- 새 워크플로는 항상 `devtools/scripts/new_workflow.py`로 시작합니다.
- `workflow_id`는 디렉터리명, 레지스트리 식별자, MCP 파일명까지 동일하게 맞춥니다.
- 공통 상태는 `ChatState`에만 두고, 워크플로 상태는 각 패키지의 `lg_state.py`에 둡니다.
- handoff 키워드는 넓지 않게 잡고 양성·음성 예시로 검증합니다.
- 운영 반영 전에는 `devtools/workflow_runner/`에서 적어도 한 번은 대화 흐름을 확인합니다.
- promotion 이후에는 전체 테스트를 다시 실행합니다.

## 7. 한 줄 요약

`devtools/`는 새 워크플로를 바로 운영 경로에 넣지 않고, 스캐폴딩, 브라우저 검증, 테스트, promotion까지 일관된 절차로 다루기 위한 개발용 staging 영역입니다.
