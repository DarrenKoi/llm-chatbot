# 파일 구조 가이드

이 문서는 팀원이 `llm_chatbot` 저장소를 처음 열었을 때 어디부터 읽어야 하는지 빠르게 이해할 수 있도록 정리한 안내서입니다.

## 한눈에 보는 구조

```text
llm_chatbot/
├── index.py
├── cube_worker.py
├── scheduler_worker.py
├── wsgi.ini
├── api/
├── devtools/
├── tests/
├── scripts/
└── doc/
```

## 루트 디렉터리

- `index.py`는 로컬 개발용 Flask 서버 실행 진입점입니다.
- `cube_worker.py`는 Cube 큐 메시지를 소비하는 워커 실행 진입점입니다.
- `scheduler_worker.py`는 스케줄 작업 전용 프로세스 실행 진입점입니다.
- `wsgi.ini`는 uWSGI 배포 설정 파일입니다.
- `requirements.txt`와 `pyproject.toml`은 의존성과 실행 환경 기준 파일입니다.
- `README.md`, `AGENTS.md`, `CLAUDE.md`는 저장소 사용 규칙과 협업 기준 문서입니다.

## `api/` 디렉터리

`api/`는 실제 운영 코드가 모여 있는 런타임 영역입니다.

### 앱 시작과 공통 설정

- `api/__init__.py`는 Flask 앱 팩토리와 공통 초기화를 담당합니다.
- `api/blueprint_loader.py`는 `router.py` 계열 파일을 자동으로 찾아 Blueprint를 등록합니다.
- `api/config.py`는 환경변수 기반 설정을 한곳에서 관리합니다.

### 메시지 입력과 응답 전달

- `api/cube/`는 Cube 요청 수신, 큐 적재, 워커 처리, 응답 전송을 담당합니다.
- `api/conversation_service.py`는 대화 이력 저장과 조회를 담당합니다.
- `api/llm/`는 LLM 호출과 시스템 프롬프트 구성을 담당합니다.

### 워크플로 실행

- `api/workflows/`는 LangGraph 기반 대화 워크플로가 모여 있는 핵심 디렉터리입니다.
- `api/workflows/lg_orchestrator.py`는 사용자 메시지를 실제 그래프 실행으로 연결하는 메인 진입점입니다.
- `api/workflows/registry.py`는 워크플로 패키지를 탐색하고 등록 정보를 읽어오는 레지스트리입니다.
- `api/workflows/start_chat/`는 기본 진입 워크플로이자 서브워크플로 라우터 역할을 합니다.
- `api/workflows/translator/`, `travel_planner/`, `chart_maker/`는 실제 업무형 서브워크플로 예시입니다.

### 운영 보조 기능

- `api/file_delivery/`는 파일 업로드, 목록 조회, 다운로드 관련 기능을 담당합니다.
- `api/profile/`는 사용자 프로필 조회와 가공을 담당합니다.
- `api/mcp/`는 MCP 도구 등록, 선택, 실행 관련 기능을 담당합니다.
- `api/scheduled_tasks/`는 스케줄 작업 등록과 실행 로직을 담당합니다.
- `api/utils/logger/`는 활동 로그와 워크플로 로그 기록을 담당합니다.

## `devtools/` 디렉터리

`devtools/`는 운영 코드에 바로 반영하기 전, 워크플로를 안전하게 설계하고 검증하기 위한 개발 전용 영역입니다.

- `devtools/workflows/`는 실험용 또는 승격 전 워크플로 패키지를 두는 위치입니다.
- `devtools/mcp/`는 dev 워크플로에서 사용하는 도구 등록 파일을 두는 위치입니다.
- `devtools/workflow_runner/`는 브라우저에서 워크플로를 직접 실행해 볼 수 있는 개발용 앱입니다.
- `devtools/scripts/new_workflow.py`는 새 워크플로 스캐폴딩 스크립트입니다.
- `devtools/scripts/promote.py`는 dev 워크플로를 `api/workflows/`로 승격하는 스크립트입니다.

## `tests/` 디렉터리

- `tests/`는 `pytest` 기반 테스트 코드가 모여 있는 위치입니다.
- 워크플로 테스트는 `test_*_lg_graph.py`, `test_lg_orchestrator.py`, `test_workflow_registry.py` 중심으로 구성되어 있습니다.
- devtools 관련 테스트는 `test_devtools_runner.py`, `test_devtools_scripts.py`, `test_devtools_workflow_examples.py`에서 확인할 수 있습니다.

## `doc/` 디렉터리

- `doc/`는 팀 온보딩 문서, 구조 설명 문서, 작업 기록 문서를 보관하는 위치입니다.
- 이번에 추가한 문서는 파일 구조, 데이터 파이프라인, LangGraph 워크플로 작성법, devtools 사용 목적을 설명합니다.

## 처음 읽을 때 추천 순서

### 서비스 전체 흐름을 빠르게 이해하고 싶을 때

1. `index.py`를 읽습니다.
2. `api/__init__.py`를 읽습니다.
3. `api/cube/router.py`와 `api/cube/service.py`를 읽습니다.
4. `api/cube/worker.py`를 읽습니다.
5. `api/workflows/lg_orchestrator.py`를 읽습니다.
6. `api/workflows/start_chat/lg_graph.py`를 읽습니다.

### 새 워크플로를 만들고 싶을 때

1. `devtools/DEVGUIDE.md`를 읽습니다.
2. `devtools/workflows/_template/`를 읽습니다.
3. `devtools/scripts/new_workflow.py`를 읽습니다.
4. `devtools/workflow_runner/`를 실행해 개발 흐름을 확인합니다.
5. 이후 `api/workflows/` 기존 예제를 읽습니다.

## 구조를 이해할 때 기억할 점

- 운영 코드는 `api/`에 있고, 실험과 사전 검증 코드는 `devtools/`에 있다는 점이 가장 중요합니다.
- 새 기능을 바로 `api/workflows/`에 넣기보다 `devtools/workflows/`에서 먼저 검증하는 흐름이 이 저장소의 기본 작업 방식입니다.
- 팀원이 구조를 읽을 때는 디렉터리 이름보다 실행 경로를 기준으로 이해하는 편이 훨씬 빠릅니다.
