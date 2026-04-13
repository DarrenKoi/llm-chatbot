# HARNESS

이 문서는 이 저장소에서 작업하는 동료가 자신의 AI 모델을 사용할 때 따라야 하는 운영 규칙입니다.

AI에게 바로 구현을 맡기기 전에, 아래 규칙을 먼저 전달하고 작업 범위를 고정하십시오. 이 문서의 목적은 모델이 저장소 구조를 오해하거나, 워크플로우 바깥 영역까지 무단으로 수정하는 일을 막는 것입니다.

## 대상

이 문서는 다음 상황을 전제로 합니다.

- 동료가 ChatGPT, Claude, Gemini, Copilot, Cursor, Codex 등 자신의 AI 모델이나 에이전트를 사용한다.
- AI에게 코드 탐색, 수정, 테스트, 커밋까지 일부 또는 전부를 맡긴다.
- 사람이 최종 검토 책임을 가진다.

AI가 무엇이든 알아서 판단하게 두지 마십시오. 먼저 범위와 금지 영역을 명시한 뒤 작업시켜야 합니다.

## 먼저 전달할 핵심 규칙

세션 시작 시 아래 내용을 AI에게 먼저 알려주십시오.

1. 이 저장소의 기본 워크플로우 진입점은 `start_chat`이다.
2. 작업 범위는 기본적으로 `api/mcp/`, `api/workflows/`, `devtools/workflows/`에 한정한다.
3. Control MCP 또는 워크플로우 로직과 직접 관련 없는 코드는 수정하지 않는다.
4. `api/config.py`, `api/__init__.py`, `index.py`, `wsgi.ini`, `requirements.txt`, `.env`, `.env.example`는 사람이 명시적으로 요청한 경우에만 수정한다.
5. 새로운 라우팅, 핸드오프, 워크플로우 제어는 `api/workflows/start_chat/`를 기준으로 설계한다.
6. 전역 설정 변경보다 노드, 그래프, 상태, 라우팅, 핸드오프 변경을 우선한다.
7. 확실하지 않으면 먼저 수정 대상 파일 목록과 이유를 제시하게 한다.

## 권장 시작 프롬프트

아래 문구를 복사해서 각자 사용하는 AI 도구의 첫 메시지나 작업 지시문에 붙여 넣는 것을 권장합니다.

```text
이 저장소에서는 start_chat이 기본 워크플로우 진입점이다.
작업 범위는 기본적으로 api/workflows/, api/workflows/start_chat/, api/mcp/, devtools/workflows/로 제한한다.
Control MCP 또는 워크플로우 로직과 직접 관련 없는 코드는 수정하지 마라.
api/config.py, api/__init__.py, index.py, wsgi.ini, requirements.txt, .env, .env.example 는 내가 명시적으로 요청할 때만 수정해라.
새 라우팅이나 핸드오프는 기존 workflow registry/orchestrator 규약을 따라라.
먼저 요청이 start_chat을 통해 어떻게 흐르는지 추적하고, 수정하려는 파일 목록과 이유를 짧게 제시한 뒤 작업해라.
```

도구가 시스템 프롬프트, 규칙 파일, 프로젝트 메모리 기능을 지원한다면 그 위치에도 같은 내용을 등록하십시오.

## 목적

이 저장소에서 AI가 작업해야 하는 핵심 범위는 Control MCP와 워크플로우 로직입니다.

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
7. AI가 대규모 리팩터링을 제안하더라도, 먼저 가장 작은 유효 변경으로 줄이게 하십시오.
8. AI가 테스트를 실행했다면 무엇을 실행했고 어떤 결과였는지 반드시 보고하게 하십시오.

## 동료 검토 체크리스트

AI가 작업을 끝냈다고 말하면, 아래 항목을 사람이 직접 확인하십시오.

1. 수정 파일이 정말로 `api/workflows/`, `api/mcp/`, `devtools/workflows/` 중심인가?
2. `start_chat` 진입 흐름을 우회하는 새 진입점이나 임시 로직이 생기지 않았는가?
3. 설정 파일, 부트스트랩, 배포 파일이 불필요하게 바뀌지 않았는가?
4. 새 워크플로우가 기존 `registry`와 `orchestrator` 규약을 따르는가?
5. devtools 예제를 프로덕션 코드처럼 설명하고 있지 않은가?
6. 테스트 또는 검증 결과가 실제 수정 범위와 맞는가?

이 체크를 통과하지 못하면 AI 출력물을 그대로 병합하지 마십시오.

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
