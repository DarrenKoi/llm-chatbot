# Project Structure

이 문서는 현재 `llm_chatbot` 저장소의 실제 코드 기준으로 프로젝트 구조를 빠르게 이해하기 위한 안내서다.  
기존 문서를 모두 정리한 뒤, 지금 남아 있는 런타임 코드와 개발 도구 중심으로 다시 작성했다.

## 1. 한눈에 보는 구조

```text
llm_chatbot/
├── index.py
├── scheduler_worker.py
├── cube_worker.py
├── wsgi.ini
├── README.md
├── requirements.txt
├── pyproject.toml
├── api/
│   ├── __init__.py
│   ├── blueprint_loader.py
│   ├── config.py
│   ├── conversation_service.py
│   ├── monitoring_service.py
│   ├── mongo.py
│   ├── cube/
│   ├── file_delivery/
│   ├── html_templates/
│   ├── llm/
│   ├── mcp/
│   ├── profile/
│   ├── scheduled_tasks/
│   ├── utils/logger/
│   └── workflows/
├── devtools/
│   ├── workflow_runner/
│   ├── workflows/
│   ├── scripts/
│   └── mcp/
├── scripts/
├── tests/
└── doc/
    └── project_structure.md
```

## 2. 실행 진입점

- `index.py`
  로컬 개발용 Flask 서버 실행 진입점이다. `api.create_application()`으로 앱을 띄운다.
- `scheduler_worker.py`
  별도 스케줄러 프로세스 진입점이다. 실제 구현은 `api.scheduler_worker`에 있다.
- `cube_worker.py`
  Cube 메시지 큐를 소비하는 워커 진입점이다. 실제 구현은 `api.cube.worker`에 있다.
- `wsgi.ini`
  uWSGI 배포 설정 파일이다. 웹 앱과 스케줄러 데몬 구성을 함께 맞출 때 기준이 된다.

## 3. 런타임 핵심 패키지: `api/`

### 3.1 앱 부트스트랩

- `api/__init__.py`
  Flask 앱 팩토리다. 템플릿 페이지, 모니터링 페이지, 워크플로 시각화 페이지를 등록하고 요청 로깅을 감싼다.
- `api/blueprint_loader.py`
  `api/` 하위의 `router.py`, `router_*.py` 파일을 자동 탐색해 Blueprint를 등록한다.
- `api/config.py`
  환경변수 기반 설정의 단일 진입점이다. Cube, LLM, MongoDB, Redis, 로깅, 파일 전달, 워크플로 상태 경로를 모두 여기서 관리한다.

### 3.2 외부 입력과 웹 라우팅

- `api/cube/`
  Cube webhook 입력 처리 계층이다.
  `router.py`는 `/api/v1/cube/receiver`를 받고, 실제 처리 위임은 `service.py`, 큐 적재/소비는 `queue.py`, `worker.py`가 담당한다.
- `api/file_delivery/`
  업로드, 목록 조회, 다운로드, 이미지 리사이즈를 담당한다.
  사용자 세션 쿠키와 저장소 메타데이터를 바탕으로 파일을 제공한다.
- `api/profile/`
  사용자 프로필 조회와 캐시 계층이다.
- `api/html_templates/`
  Flask가 직접 렌더링하는 HTML 템플릿이다.
  현재 랜딩, 대화 이력, 모니터, 스케줄 작업, 파일 전달 화면이 있다.

### 3.3 대화/모델 계층

- `api/conversation_service.py`
  대화 이력 저장과 조회를 담당한다. 설정에 따라 MongoDB 또는 로컬/메모리 기반 저장소를 사용할 수 있다.
- `api/llm/`
  모델 호출과 시스템 프롬프트 계층이다.
  `service.py`가 호출 래퍼 역할을 하고, `prompt/system.py`가 기본 시스템 프롬프트를 관리한다.
- `api/workflows/`
  현재 대화 처리의 중심이다.
  LangGraph 기반 워크플로 오케스트레이션과 세부 워크플로 구현이 모여 있다.

### 3.4 워크플로 계층 상세

- `api/workflows/lg_orchestrator.py`
  Cube 워커가 호출하는 메인 오케스트레이터다.
  사용자 메시지를 스레드 단위 상태에 연결하고, 기존 대화가 이어지는 경우 resume 흐름으로 처리한다.
- `api/workflows/langgraph_checkpoint.py`
  LangGraph 체크포인터와 스레드 식별 규칙을 제공한다.
- `api/workflows/registry.py`
  사용 가능한 워크플로 등록 정보 관리 지점이다.
- `api/workflows/graph_visualizer.py`
  워크플로 목록과 HTML 시각화 출력을 만든다.
- `api/workflows/start_chat/`
  기본 진입 워크플로다. 의도 판별과 하위 워크플로 전환의 출발점 역할을 한다.
- `api/workflows/translator/`
  번역 전용 LangGraph 워크플로다.
- `api/workflows/travel_planner/`
  여행 계획 전용 워크플로다.

### 3.5 운영/인프라 보조 계층

- `api/scheduled_tasks/`
  APScheduler 작업 등록, 분산 락, 점검용 스냅샷, 실제 task 구현을 담는다.
- `api/monitoring_service.py`
  모니터링 화면에 보여줄 런타임 스냅샷을 만든다.
- `api/mcp/`
  MCP 클라이언트, 레지스트리, 로컬 툴 실행기, 툴 선택 로직을 담는다.
- `api/mongo.py`
  MongoDB 연결 유틸리티다.
- `api/utils/logger/`
  활동 로그 포맷, 경로, 로거 초기화와 기록 함수를 제공한다.

## 4. 개발 보조 영역

### 4.1 `devtools/`

런타임 앱과 분리된 개발용 실험 공간이다.

- `devtools/workflow_runner/`
  브라우저에서 워크플로를 직접 실행하고 상태를 확인하기 위한 개발용 앱이다.
- `devtools/workflows/`
  새 워크플로 템플릿과 예제 구현이 있다.
- `devtools/scripts/`
  워크플로 생성, 승격 등 반복 작업을 줄이는 보조 스크립트가 있다.
- `devtools/mcp/`
  개발 중 사용하는 MCP 관련 템플릿과 보조 코드가 있다.

### 4.2 `scripts/`

저장소 루트의 단발성 보조 스크립트다.

- `scripts/check_tool_calling.py`
  툴 호출 관련 점검 스크립트다.
- `scripts/sync_to_bitbucket.py`
  저장소 동기화 작업용 스크립트다.

## 5. 테스트 구조

- `tests/`
  `pytest` 기반 전체 테스트 스위트다.
- `tests/conftest.py`
  공통 fixture와 테스트 초기화 로직이 들어 있다.
- 주요 테스트 그룹
  - Cube 입력/워커: `test_cube_router.py`, `test_cube_service.py`, `test_cube_worker.py`
  - 워크플로: `test_start_chat_lg_graph.py`, `test_translator_lg_graph.py`, `test_travel_planner_lg_graph.py`, `test_lg_orchestrator.py`
  - 파일 전달: `test_file_delivery_routes.py`, `test_file_delivery_service.py`
  - 설정/인프라: `test_config.py`, `test_scheduler.py`, `test_langgraph_checkpoint.py`, `test_router_loader.py`
  - 개발 도구: `test_devtools_runner.py`, `test_devtools_scripts.py`, `test_devtools_workflow_examples.py`

## 6. 요청 흐름 기준으로 보는 읽기 순서

Cube 메시지 한 건이 어떻게 처리되는지 따라가려면 아래 순서가 가장 빠르다.

1. `index.py`
2. `api/__init__.py`
3. `api/blueprint_loader.py`
4. `api/cube/router.py`
5. `api/cube/service.py`
6. `api/cube/queue.py` / `api/cube/worker.py`
7. `api/workflows/lg_orchestrator.py`
8. `api/workflows/start_chat/lg_graph.py`
9. 필요한 하위 워크플로 패키지 (`translator`, `travel_planner`)

파일 업로드 흐름을 보려면 아래 순서가 적절하다.

1. `api/file_delivery/router.py`
2. `api/file_delivery/file_delivery_service.py`
3. 관련 테스트 `tests/test_file_delivery_routes.py`, `tests/test_file_delivery_service.py`

스케줄 작업을 보려면 아래 순서가 적절하다.

1. `scheduler_worker.py`
2. `api/scheduler_worker.py`
3. `api/scheduled_tasks/_registry.py`
4. `api/scheduled_tasks/tasks/`

## 7. 지금 구조의 핵심 요약

- 웹 서버는 Flask 앱 팩토리 패턴으로 구성되어 있다.
- 실제 기능 라우터는 `api/` 하위에서 자동 등록된다.
- 대화 처리 중심은 `api/workflows/`의 LangGraph 계층이다.
- Cube 입력, 파일 전달, 스케줄러, MCP, 로깅이 각각 독립 패키지로 분리되어 있다.
- `devtools/`는 운영 코드와 분리된 실험/개발 지원 영역이다.
- `doc/`는 현재 이 구조 문서부터 다시 정리하는 상태다.
