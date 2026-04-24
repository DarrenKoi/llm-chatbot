# 파일 구조 가이드

> 최종 업데이트: 2026-04-17

이 문서는 `shared_docs/`에서 프로젝트 구조를 빠르게 공유하기 위한 요약본입니다.
팀원이 실제로 볼 수 있는 경로 기준으로 정리했으며, top-level에서는 `api/`, `devtools/`, `shared_docs/`와 실행 파일만 설명합니다.

## 1. 한눈에 보는 구조

```text
llm_chatbot/
├── index.py
├── cube_worker.py
├── scheduler_worker.py
├── wsgi.ini
├── requirements.txt
├── api/
├── devtools/
└── shared_docs/
```

## 2. 실행 진입점

- `index.py`
  로컬 개발용 Flask 서버 실행 진입점입니다. `api.create_application()`으로 앱을 띄웁니다.
- `cube_worker.py`
  Cube 메시지 큐를 소비하는 워커 진입점입니다. 실제 구현은 `api.cube.worker`에 있습니다.
- `scheduler_worker.py`
  별도 스케줄러 프로세스 진입점입니다. 실제 구현은 `api.scheduler_worker`에 있습니다.
- `wsgi.ini`
  uWSGI 배포 설정 파일입니다.
- `requirements.txt`
  배포 및 실행 환경에서 사용하는 Python 의존성 목록입니다.

## 3. 런타임 핵심 패키지: `api/`

`api/`는 실제 운영 코드가 모여 있는 런타임 영역입니다.

### 앱 부트스트랩과 공통 설정

- `api/__init__.py`
  Flask 앱 팩토리입니다. 템플릿 페이지, 모니터링 페이지, 워크플로 시각화 페이지를 등록하고 요청 로깅을 감쌉니다.
- `api/blueprint_loader.py`
  `api/` 하위의 `router.py`, `router_*.py` 파일을 자동 탐색해 Blueprint를 등록합니다.
- `api/config.py`
  환경변수 기반 설정의 단일 진입점입니다. Cube, LLM, MongoDB, Redis, 로깅, 파일 전달, 워크플로 상태 경로를 모두 여기서 관리합니다.

### 외부 입력과 웹 라우팅

- `api/cube/`
  Cube webhook 입력 처리 계층입니다. `router.py`는 `/api/v1/cube/receiver`를 받고, `service.py`, `queue.py`, `worker.py`가 실제 처리와 큐 소비를 담당합니다.
- `api/file_delivery/`
  업로드, 목록 조회, 다운로드, 이미지 리사이즈를 담당합니다.
- `api/profile/`
  사용자 프로필 조회와 캐시 계층입니다.
- `api/html_templates/`
  Flask가 직접 렌더링하는 HTML 템플릿입니다.

### 대화와 모델 계층

- `api/conversation_service.py`
  대화 이력 저장과 조회를 담당합니다. 설정에 따라 MongoDB, 로컬 파일, 메모리 백엔드를 사용할 수 있습니다.
- `api/llm/`
  모델 호출과 시스템 프롬프트 계층입니다.
- `api/workflows/`
  현재 대화 처리의 중심입니다. LangGraph 기반 워크플로 오케스트레이션과 세부 워크플로 구현이 모여 있습니다.

### 워크플로 계층 상세

- `api/workflows/lg_orchestrator.py`
  Cube 워커가 호출하는 메인 오케스트레이터입니다.
- `api/workflows/langgraph_checkpoint.py`
  LangGraph 체크포인터와 thread 식별 규칙을 제공합니다.
- `api/workflows/registry.py`
  사용 가능한 워크플로 패키지를 자동 탐색하고 정규화합니다.
- `api/workflows/graph_visualizer.py`
  워크플로 목록과 HTML 시각화 출력을 만듭니다.
- `api/workflows/start_chat/`
  기본 진입 워크플로입니다. 일반 대화 처리와 하위 워크플로 handoff의 출발점입니다.
- `api/workflows/translator/`
  번역 전용 워크플로입니다.

### 운영 보조 계층

- `api/scheduled_tasks/`
  APScheduler 작업 등록, 분산 락, 점검 스냅샷, 실제 task 구현을 담습니다.
- `api/monitoring_service.py`
  모니터링 화면에 보여줄 런타임 스냅샷을 만듭니다.
- `api/mcp/`
  MCP 클라이언트, 레지스트리, 로컬 툴 실행기, 툴 선택 로직을 담습니다.
- `api/mongo.py`
  MongoDB 연결 유틸리티입니다.
- `api/utils/logger/`
  활동 로그 포맷, 경로, 로거 초기화와 기록 함수를 제공합니다.

## 4. 개발 보조 영역

### `devtools/`

`devtools/`는 운영 코드와 분리된 개발용 실험 공간입니다.

- `devtools/workflow_runner/`
  브라우저에서 워크플로를 직접 실행하고 상태를 확인하는 개발용 앱입니다.
- `devtools/workflows/`
  새 워크플로 템플릿과 예제 구현이 있습니다.
- `devtools/scripts/`
  워크플로 생성, 승격 등 반복 작업을 줄이는 스크립트가 있습니다.
- `devtools/mcp/`
  개발 중 사용하는 MCP 템플릿과 보조 코드가 있습니다.
- `devtools/var/`
  dev runner가 사용하는 대화 이력과 상태 저장 경로입니다.

### `shared_docs/`

공유용 요약 문서를 두는 영역입니다.

- `shared_docs/file_structure.md`
  팀원 가시 범위 기준의 구조 설명입니다.
- `shared_docs/data_pipeline.md`
  Cube 입력부터 LangGraph 실행과 저장까지의 흐름을 설명합니다.
- `shared_docs/workflow_build_with_langgraph.md`
  LangGraph 워크플로 설계와 등록 원칙을 설명합니다.
- `shared_docs/devtools.md`
  `devtools/` 기반 개발 절차를 설명합니다.

## 5. 추천 읽기 순서

### Cube 메시지 처리 흐름을 이해하고 싶을 때

1. `index.py`
2. `api/__init__.py`
3. `api/blueprint_loader.py`
4. `api/cube/router.py`
5. `api/cube/service.py`
6. `api/cube/queue.py`
7. `api/cube/worker.py`
8. `api/workflows/lg_orchestrator.py`
9. `api/workflows/start_chat/lg_graph.py`
10. 필요한 하위 워크플로 패키지

### 새 워크플로를 만들고 싶을 때

1. `devtools/DEVGUIDE.md`
2. `devtools/workflows/_template/`
3. `devtools/scripts/new_workflow.py`
4. `devtools/workflow_runner/`
5. 이후 `api/workflows/` 기존 예제

### 파일 전달 흐름을 보고 싶을 때

1. `api/file_delivery/router.py`
2. `api/file_delivery/file_delivery_service.py`

## 6. 구조를 이해할 때 기억할 점

- 웹 서버는 Flask 앱 팩토리 패턴으로 구성되어 있습니다.
- 실제 기능 라우터는 `api/` 하위에서 자동 등록됩니다.
- 대화 처리의 중심은 `api/workflows/`의 LangGraph 계층입니다.
- Cube 입력, 파일 전달, 스케줄러, MCP, 로깅이 각각 `api/` 아래에서 독립 패키지로 분리되어 있습니다.
- `devtools/`는 운영 코드와 분리된 실험·개발 지원 영역입니다.
- `shared_docs/`는 팀 공유용으로 압축한 설명 문서 영역입니다.
