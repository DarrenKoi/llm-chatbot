# HARNESS

이 문서는 이 저장소에서 작업하는 동료가 자신의 AI 모델을 사용할 때 따라야 하는 운영 규칙입니다.

AI에게 바로 구현을 맡기기 전에, 아래 규칙을 먼저 전달하고 작업 범위를 고정하십시오. 이 문서의 목적은 모델이 저장소 구조를 오해하거나, 워크플로우 바깥 영역까지 무단으로 수정하는 일을 막는 것입니다.

## 대상

이 문서는 다음 상황을 전제로 합니다.

- 동료가 ChatGPT, Claude, Gemini, Copilot, Cursor, Codex 등 자신의 AI 모델이나 에이전트를 사용한다.
- AI에게 코드 탐색, 수정, 테스트, 커밋까지 일부 또는 전부를 맡긴다.
- 사람이 최종 검토 책임을 가진다.

AI가 무엇이든 알아서 판단하게 두지 마십시오. 먼저 범위와 금지 영역을 명시한 뒤 작업시켜야 합니다.

## 최근 변경 안내 (2026-04-28)

워크플로 / MCP 패키지가 최근 정리되었습니다. 이전 경로로 import하던 코드는 즉시 새 경로로 갱신해 주십시오. 호환성 shim도 제거되었기 때문에 자동으로 떨어지지 않습니다.

| 이전 경로 | 현재 경로 |
|---|---|
| `api.mcp` / `api/mcp/` | `api.mcp_runtime` / `api/mcp_runtime/` |
| `devtools.mcp` / `devtools/mcp/` | `devtools.mcp_runtime` / `devtools/mcp_runtime/` |

- 호환성 shim(`api/mcp/__init__.py`)이 제거되었으므로 `from api.mcp import ...` 형태의 import는 즉시 ImportError가 납니다.
- 워크플로/MCP 영역은 최근에 직접 정비된 코드입니다. AI 도구가 캐시된 옛 구조나 학습 데이터의 옛 패키지명에 의존하지 않도록, 작업 범위와 경로를 항상 명시적으로 지정하십시오.
- 새 코드 작성 전에 아래 공유 문서를 먼저 확인해 주십시오:
  - [`shared_docs/file_structure.md`](./shared_docs/file_structure.md) — 현재 디렉터리 구조
  - [`shared_docs/workflow_build_with_langgraph.md`](./shared_docs/workflow_build_with_langgraph.md) — 워크플로 작성 핸드북
  - [`shared_docs/workflow_catalog.md`](./shared_docs/workflow_catalog.md) — 등록된 워크플로 목록과 인프라 소유권 정책
  - [`shared_docs/devtools.md`](./shared_docs/devtools.md) — devtools 기반 개발 절차

## 먼저 전달할 핵심 규칙

세션 시작 시 아래 내용을 AI에게 먼저 알려주십시오.

1. 이 저장소의 기본 워크플로우 진입점은 `start_chat`이다.
2. 작업 범위는 기본적으로 `api/mcp_runtime/`, `api/workflows/`, `devtools/workflows/`에 한정한다.
3. Control MCP 또는 워크플로우 로직과 직접 관련 없는 코드는 수정하지 않는다.
4. `api/config.py`, `api/__init__.py`, `index.py`, `wsgi.ini`, `requirements.txt`, `.env`, `.env.example`는 사람이 명시적으로 요청한 경우에만 수정한다.
5. 새로운 라우팅, 핸드오프, 워크플로우 제어는 `api/workflows/start_chat/`를 기준으로 설계한다.
6. 전역 설정 변경보다 노드, 그래프, 상태, 라우팅, 핸드오프 변경을 우선한다.
7. 확실하지 않으면 먼저 수정 대상 파일 목록과 이유를 제시하게 한다.
8. `api/workflows/` 루트의 인프라 파일(아래 "owner 통보 필수 인프라 파일" 섹션 참고)은 Daeyoung 사전 승인 없이 수정하지 않는다.

## 권장 시작 프롬프트

아래 문구를 복사해서 각자 사용하는 AI 도구의 첫 메시지나 작업 지시문에 붙여 넣는 것을 권장합니다.

```text
이 저장소에서는 start_chat이 기본 워크플로우 진입점이다.
작업 범위는 기본적으로 api/workflows/, api/workflows/start_chat/, api/mcp_runtime/, devtools/workflows/로 제한한다.
Control MCP 또는 워크플로우 로직과 직접 관련 없는 코드는 수정하지 마라.
api/config.py, api/__init__.py, index.py, wsgi.ini, requirements.txt, .env, .env.example 는 내가 명시적으로 요청할 때만 수정해라.
새 라우팅이나 핸드오프는 기존 workflow registry/orchestrator 규약을 따라라.
api/workflows/ 루트의 인프라 파일(registry.py, lg_orchestrator.py, lg_state.py, models.py, langgraph_checkpoint.py, intent_utils.py, graph_visualizer.py, __init__.py)과 devtools/workflow_runner/dev_orchestrator.py 는 Daeyoung 사전 승인 없이 수정하지 마라. 수정이 필요해 보이면 먼저 사유를 제시하고 승인을 요청해라.
api/mcp/, devtools/mcp/ 경로는 더 이상 존재하지 않는다. 코드나 import에서 이 경로가 등장하면 즉시 멈추고 보고해라. 새 경로는 api/mcp_runtime/, devtools/mcp_runtime/ 이다.
api/ 와 devtools/ 사이의 import는 양방향 모두 금지한다. 새 코드에서 from api.* 를 devtools/ 안에 추가하거나 from devtools.* 를 api/ 안에 추가하지 마라. 기존 cross-import를 발견하면 단독으로 고치지 말고 먼저 보고해라.
워크플로/MCP 영역은 최근에 정비된 코드이므로, 학습 데이터나 캐시된 구조 대신 현재 저장소의 shared_docs/ 와 코드를 직접 읽고 작업해라.
먼저 요청이 start_chat을 통해 어떻게 흐르는지 추적하고, 수정하려는 파일 목록과 이유를 짧게 제시한 뒤 작업해라.
```

도구가 시스템 프롬프트, 규칙 파일, 프로젝트 메모리 기능을 지원한다면 그 위치에도 같은 내용을 등록하십시오.

## 목적

이 저장소에서 AI가 작업해야 하는 핵심 범위는 Control MCP와 워크플로우 로직입니다.

- 주요 범위: `api/mcp_runtime/`
- 주요 범위: `api/workflows/`
- 참고용 작성 범위: `devtools/workflows/`
- 시작 지점: `start_chat`

작업이 Control MCP 또는 워크플로우에 명확히 속하지 않는다면, 범위를 다시 정의하기 전까지 코드를 수정하지 마십시오.

## 첫 번째 원칙

이 저장소는 `start_chat`에서 워크플로우 실행을 시작합니다.

- 기본 워크플로우 진입점은 `start_chat`입니다.
- 새로운 라우팅, 핸드오프, 워크플로우 제어는 `api/workflows/start_chat/`를 기준으로 설계해야 합니다.
- 사용자 요청은 먼저 `start_chat`으로 들어오고, 이후에는 명시적인 워크플로우 제어를 통해서만 다른 워크플로우로 이동한다고 가정합니다.

임시방편의 우회 경로로 이 진입 흐름을 건너뛰지 마십시오.

## 폴더 제어 범위

수정 대상은 워크플로우와 MCP 제어 표면으로 제한해야 합니다.

### 작업 가능 영역

- `api/workflows/<workflow_id>/` (각 워크플로 패키지 내부, 예: `lg_graph.py`, `lg_state.py`, `tools.py`, `prompts.py` 등)
- `api/workflows/start_chat/`
- `api/mcp_runtime/`
- `devtools/workflows/`
- `devtools/DEVGUIDE.md`

> 루트의 인프라 파일(`registry.py`, `lg_orchestrator.py` 등)은 아래 "owner 통보 필수" 표 참고.

### 기본 수정 금지 영역

사람이 명시적으로 요청한 경우가 아니라면 아래 항목은 수정하지 마십시오.

- `api/config.py`
- `api/__init__.py`
- `index.py`
- `wsgi.ini`
- `requirements.txt`
- `.env`
- `.env.example`
- 일반적인 앱 부트스트랩 또는 배포 설정
- MCP 및 워크플로우 밖의 관련 없는 서비스 패키지

### owner 통보 필수 인프라 파일 (Daeyoung 사전 승인)

아래 파일들은 작업 가능 영역(`api/workflows/`, `devtools/workflow_runner/`) 안에 있지만, **워크플로우 전체에 영향을 미치는 코어 인프라**입니다. 수정 전 반드시 Daeyoung에게 사유를 공유하고 승인을 받아야 합니다. AI 도구도 이 파일들을 단독 수정하지 말고, 변경이 필요해 보이면 먼저 변경 계획을 제시하십시오.

| 파일 | 역할 |
|---|---|
| `api/workflows/registry.py` | 워크플로 자동 발견 + 정의 정규화 |
| `api/workflows/lg_orchestrator.py` | Cube 워커 진입점, 루트 그래프 invoke·resume |
| `api/workflows/lg_state.py` | 모든 워크플로 공통 `ChatState` |
| `api/workflows/models.py` | `WorkflowReply` 등 응답 계약 |
| `api/workflows/langgraph_checkpoint.py` | 체크포인터 팩토리, `thread_id` 규칙 |
| `api/workflows/intent_utils.py` | 의도 분류 공통 유틸 |
| `api/workflows/graph_visualizer.py` | 그래프 시각화 도구 |
| `api/workflows/__init__.py` | 워크플로 패키지 초기화 |
| `devtools/workflow_runner/dev_orchestrator.py` | dev 오케스트레이터 (위 인프라와 짝) |

**자유 수정 영역(통보 불필요):** `api/workflows/<workflow_id>/` 패키지 내부 파일과 `devtools/workflows/<workflow_id>/` 패키지 내부 파일. 새 워크플로 추가는 자동 발견 구조라 위 인프라 파일을 건드릴 필요가 없습니다.

**왜 이 정책이 있나:** 이 인프라 레이어는 멀티턴 지속성, 체크포인터 호환성, 자동 발견 계약 등 한눈에 보이지 않는 invariant를 다수 포함합니다. 부분 수정이 다른 워크플로의 가정을 깨면 디버깅 비용이 큽니다. 자세한 배경과 영향 범위는 [`shared_docs/workflow_catalog.md`](./shared_docs/workflow_catalog.md)의 "인프라 파일 소유권 정책" 섹션을 참조하십시오.

## `api/` ↔ `devtools/` 격리 정책

`api/`와 `devtools/`는 서로 독립적으로 동작해야 합니다. 두 패키지 사이의 import는 양방향 모두 금지합니다.

- `api/*` 모듈은 `devtools.*`를 import하지 않습니다.
- `devtools/*` 모듈은 `api.*`를 import하지 않습니다 (예: `from api.workflows.lg_state import ChatState` 같은 형태도 금지).
- 두 영역에서 공통으로 필요한 타입·유틸리티는 한쪽에 두고 다른 쪽에서 import하는 방식 대신, 각 영역이 자체적으로 정의하거나 명시적으로 동기화 가능한 정의를 둡니다.
- promote 스크립트가 `devtools.mcp_runtime.*` → `api.mcp_runtime.*`로 치환할 때도, dev 전용 보조 import가 함께 운영으로 끌려 들어가지 않도록 검토합니다.
- **기존 cross-import는 점진 정리 대상**입니다. 새로 작성하는 코드에서는 이 규칙을 위반하지 마십시오. 기존 cross-import를 발견하면 즉시 고치지 말고, 먼저 owner(Daeyoung)에게 보고한 뒤 정리 계획을 세우십시오.

**왜 이 정책이 있나:** 운영(`api/`)이 dev 코드(`devtools/`)에 우연히 의존해 배포 사고가 나는 것을 막고, dev 영역이 운영 인프라 변경마다 깨지지 않도록 하기 위함입니다. 두 영역의 결합을 풀어 두면 운영 코드를 외부 컨테이너로 분리하거나 dev 도구를 별도 저장소로 이전하기도 쉬워집니다.

## 작업 규칙

1. 먼저 요청이 `api/workflows/start_chat/`를 통해 어떻게 흐르는지 추적합니다.
2. 전역 설정 변경보다 라우팅, 핸드오프, 노드, 그래프, 상태 변경을 우선합니다.
3. 수정은 워크플로우 패키지, devtools 워크플로우 예제, MCP 제어 모듈에 국한합니다.
4. 새 워크플로우를 추가할 때는 별도 시스템을 만들지 말고 기존 워크플로우 등록 규약을 따릅니다.
5. `start_chat`에서 핸드오프할 때는 확립된 워크플로우 레지스트리와 오케스트레이터 동작을 사용합니다.
6. 사람이 명시적으로 승인하지 않는 한 기존 기본 설정은 유지합니다.
7. AI가 대규모 리팩터링을 제안하더라도, 먼저 가장 작은 유효 변경으로 줄이게 하십시오.
8. AI가 테스트를 실행했다면 무엇을 실행했고 어떤 결과였는지 반드시 보고하게 하십시오.

## 동료 검토 체크리스트

AI가 작업을 끝냈다고 말하면, 아래 항목을 사람이 직접 확인하십시오.

1. 수정 파일이 정말로 `api/workflows/`, `api/mcp_runtime/`, `devtools/workflows/` 중심인가?
2. `start_chat` 진입 흐름을 우회하는 새 진입점이나 임시 로직이 생기지 않았는가?
3. 설정 파일, 부트스트랩, 배포 파일이 불필요하게 바뀌지 않았는가?
4. 새 워크플로우가 기존 `registry`와 `orchestrator` 규약을 따르는가?
5. devtools 예제를 프로덕션 코드처럼 설명하고 있지 않은가?
6. 테스트 또는 검증 결과가 실제 수정 범위와 맞는가?
7. `api/workflows/` 루트의 인프라 파일을 Daeyoung 사전 승인 없이 수정하지 않았는가? (위 "owner 통보 필수 인프라 파일" 섹션 참고)

이 체크를 통과하지 못하면 AI 출력물을 그대로 병합하지 마십시오.

## Devtools와 API 정렬

`devtools/`의 워크플로우 작성 경험은 `api/`의 실제 런타임과 닮아 있어야 합니다.

- 최소 구조 예제: `devtools/workflows/_template/`
- 멀티턴 interrupt/resume 예제: `devtools/workflows/travel_planner_example/`
- Richnotification payload 예제: `devtools/workflows/richinotification_test/`
- 파일 분리 컨벤션: `__init__.py`, `lg_graph.py`, `lg_state.py`, 필요 시 `tools.py`, `prompts.py`, `llm_decision.py`, `constants.py` 등 보조 파일 추가.
- `devtools/workflows/`에서는 승격이 쉽도록 패키지 내부 상대 임포트를 우선하고, 공유 타입은 `from api.workflows.lg_state import ChatState`로 가져옵니다.
- `api/workflows/`에서는 진입점과 핸드오프 중심을 `start_chat`에 둡니다.

이 예제 폴더들은 동료가 기본 앱 설정을 건드리지 않고도 구조와 코딩 스타일을 복사할 수 있도록 존재합니다.

## Devtools 응답 규칙

작업이 `devtools/`에서 처리되는 경우, 답변에서 그 사실을 명시해야 합니다.

- `This is done via devtools.` 같은 명확한 표현을 사용합니다.
- 변경 내용을 설명할 때 관련 `devtools/...` 경로를 언급합니다.
- devtools 작업을 이미 프로덕션 런타임에 연결된 것처럼 설명하지 마십시오.
- 코드가 devtools 프로토타입 또는 예제에 불과하다면, 먼저 devtools 작업임을 표시합니다.

## 워크플로우 작성 방법

새 워크플로우를 만들 때는 다음 순서를 따릅니다.

1. 기본 구조는 `devtools/workflows/_template/`, 멀티턴 흐름은 `devtools/workflows/travel_planner_example/`, payload 조립은 `devtools/workflows/richinotification_test/`를 출발점으로 사용합니다.
2. 구현은 먼저 해당 워크플로 폴더 내부에 유지합니다.
3. 상태는 `lg_state.py`에 `ChatState`를 상속해 정의합니다.
4. 노드 함수와 `StateGraph` 빌더(`build_lg_graph`)는 `lg_graph.py`에서 구성합니다.
5. 보조 파일(`tools.py`, `prompts.py`, `llm_decision.py`, `constants.py` 등)은 실제 필요할 때만 추가합니다.
6. `__init__.py`에 `get_workflow_definition()`을 export하면 레지스트리가 자동 발견합니다.
7. 안정화 후 `devtools/scripts/promote.py`로 `api/workflows/`에 승격합니다.

## 결정 경계

먼저 제어 폴더 내부에서 가능한 가장 작은 유효 변경을 선택합니다.

- 앱 전역 코드를 건드리기 전에 `api/workflows/start_chat/`에서 먼저 수정합니다.
- 관련 없는 통합을 건드리기 전에 `api/mcp_runtime/`에서 먼저 수정합니다.
- 부트스트랩을 바꾸기 전에 워크플로우 노드와 라우팅 확장을 우선합니다.

## 아키텍처 상기

현재 기대되는 흐름:

`Cube -> queue -> worker -> lg_orchestrator -> start_chat -> handoff/next workflow`

이 제어 체인을 존중하십시오.

## 출력 편향

다음 개선에 기여하는 코드를 우선합니다.

- 워크플로우 진입 처리
- 워크플로우 라우팅
- 워크플로우 핸드오프
- MCP 도구 제어
- 상태 전이
- 제어 계층의 안전성과 명확성

주로 다음만 바꾸는 작업은 피하십시오.

- 환경 설정
- 배포 설정
- 기본 애플리케이션 배선
- 관련 없는 API 도메인

## 확실하지 않을 때

작업이 아래 위치 중 어디에서 처리되어야 하는지 먼저 확인하십시오.

- `api/workflows/`
- `api/mcp_runtime/`

해당하지 않는다면 스스로 범위를 넓히지 마십시오.
