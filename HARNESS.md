# HARNESS

이 문서는 이 저장소에서 작업하는 동료 LLM을 위한 사전 작업 가이드입니다.

## 목적

Control MCP와 워크플로우 로직에만 작업합니다.

- 주요 범위: `api/mcp/`
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

- `api/workflows/`
- `api/workflows/start_chat/`
- `api/workflows/*/graph.py`
- `api/workflows/*/nodes.py`
- `api/workflows/*/state.py`
- `api/workflows/*/routing.py`
- `api/workflows/registry.py`
- `api/workflows/orchestrator.py`
- `api/mcp/`
- `devtools/workflows/`
- `devtools/DEVGUIDE.md`

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

## 작업 규칙

1. 먼저 요청이 `api/workflows/start_chat/`를 통해 어떻게 흐르는지 추적합니다.
2. 전역 설정 변경보다 라우팅, 핸드오프, 노드, 그래프, 상태 변경을 우선합니다.
3. 수정은 워크플로우 패키지, devtools 워크플로우 예제, MCP 제어 모듈에 국한합니다.
4. 새 워크플로우를 추가할 때는 별도 시스템을 만들지 말고 기존 워크플로우 등록 규약을 따릅니다.
5. `start_chat`에서 핸드오프할 때는 확립된 워크플로우 레지스트리와 오케스트레이터 동작을 사용합니다.
6. 사람이 명시적으로 승인하지 않는 한 기존 기본 설정은 유지합니다.

## Devtools와 API 정렬

`devtools/`의 워크플로우 작성 경험은 `api/`의 실제 런타임과 닮아 있어야 합니다.

- 규칙 기반 워크플로우의 기준 예제로 `devtools/workflows/travel_planner_example/`를 사용합니다.
- MCP 도구도 사용하는 워크플로우의 기준 예제로 `devtools/workflows/translator_example/`를 사용합니다.
- 두 폴더 모두에서 파일 분리는 익숙한 형태를 유지합니다: `__init__.py`, `graph.py`, `nodes.py`, `state.py`, 필요 시 `tools.py`, `routing.py`, `prompts.py` 같은 보조 파일을 추가합니다.
- `devtools/workflows/`에서는 나중에 쉽게 승격할 수 있도록 워크플로우 패키지 내부의 상대 임포트를 선호합니다.
- `api/workflows/`에서는 프로덕션 진입점과 핸드오프 경로의 중심을 `start_chat`에 둡니다.

이 예제 폴더들은 동료가 기본 앱 설정을 건드리지 않고도 구조와 코딩 스타일을 복사할 수 있도록 존재합니다.

## Devtools 응답 규칙

작업이 `devtools/`에서 처리되는 경우, 답변에서 그 사실을 명시해야 합니다.

- `This is done via devtools.` 같은 명확한 표현을 사용합니다.
- 변경 내용을 설명할 때 관련 `devtools/...` 경로를 언급합니다.
- devtools 작업을 이미 프로덕션 런타임에 연결된 것처럼 설명하지 마십시오.
- 코드가 devtools 프로토타입 또는 예제에 불과하다면, 먼저 devtools 작업임을 표시합니다.

## 워크플로우 작성 방법

새 워크플로우를 만들 때는 다음 순서를 따릅니다.

1. `devtools/workflows/travel_planner_example/` 또는 `devtools/workflows/translator_example/`를 출발점으로 사용합니다.
2. 구현은 먼저 해당 워크플로우 폴더 내부에 유지합니다.
3. 상태는 `state.py`에 정의합니다.
4. 노드 동작은 `nodes.py`에 넣습니다.
5. 그래프 연결은 `graph.py`에서 구성합니다.
6. 선택적 보조 파일은 워크플로우에 실제로 필요할 때만 추가합니다.
7. 워크플로우 형태가 안정화된 뒤 `api/workflows/start_chat/`에서 연결하거나 핸드오프합니다.

예제 워크플로우가 `tools.py` 같은 보조 모듈을 사용한다면, 모든 내용을 한 파일에 몰아넣지 말고 그 패턴을 유지하십시오.

## 결정 경계

먼저 제어 폴더 내부에서 가능한 가장 작은 유효 변경을 선택합니다.

- 앱 전역 코드를 건드리기 전에 `api/workflows/start_chat/`에서 먼저 수정합니다.
- 관련 없는 통합을 건드리기 전에 `api/mcp/`에서 먼저 수정합니다.
- 부트스트랩을 바꾸기 전에 워크플로우 노드와 라우팅 확장을 우선합니다.

## 아키텍처 상기

현재 기대되는 흐름:

`Cube -> queue -> worker -> orchestrator -> start_chat -> handoff/next workflow`

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
- `api/mcp/`

해당하지 않는다면 스스로 범위를 넓히지 마십시오.
