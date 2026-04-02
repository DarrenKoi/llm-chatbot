# API Package Structure

이 문서는 `api/` 패키지의 구조와 각 하위 모듈의 책임을 정리한다.

## 상위 구조

```text
api/
├── __init__.py
├── blueprint_loader.py
├── config.py
├── conversation_service.py
├── monitoring_service.py
├── archive/
├── cube/
├── file_delivery/
├── llm/
├── mcp/
├── scheduled_tasks/
├── html_templates/
├── utils/
└── workflows/
```

## 공용 파일

- `api/__init__.py`: Flask 앱 생성, 기본 페이지 등록, blueprint 자동 등록, 요청/에러 로깅을 담당한다.
- `api/blueprint_loader.py`: `router.py` 계열 파일을 찾아 Blueprint를 자동 로드한다.
- `api/config.py`: Cube, LLM, Redis, MongoDB, Scheduler, 로그, 파일 저장 경로 등 환경 기반 설정을 모은다.
- `api/conversation_service.py`: 대화 이력을 관리하며 MongoDB 또는 메모리 백엔드를 사용한다.
- `api/monitoring_service.py`: 모니터링 페이지에서 사용하는 상태 요약 정보를 구성한다.

## 하위 패키지

### `api/cube/`

Cube 연동의 중심 패키지다.

- `router.py`: `/api/v1/cube/receiver` 요청을 받는다.
- `payload.py`: Cube 요청 payload 파싱과 필드 추출을 담당한다.
- `service.py`: 수신 메시지 처리 흐름을 조합한다.
- `client.py`: Cube API 호출을 수행한다.
- `queue.py`: Redis 기반 큐 적재를 담당한다.
- `worker.py`: 큐에서 메시지를 꺼내 워크플로우를 실행한다.
- `models.py`: Cube 메시지 관련 모델을 정의한다.

### `api/file_delivery/`

파일 업로드와 다운로드 기능을 담당한다.

- `router.py`: 업로드 API, 파일 제공 API, 파일 전달 페이지를 제공한다.
- `file_delivery_service.py`: 저장, 메타데이터 관리, 이미지 리사이즈/썸네일 처리의 핵심 로직이 위치한다.
- `__init__.py`: 외부에서 쓰는 파일 전달 기능을 재노출한다.

### `api/archive/`

검색/아카이브 관련 기능이 모여 있다.

- `extractor.py`: 아카이브 데이터 추출 로직
- `service.py`: 아카이브 처리 서비스
- `opensearch_client.py`: OpenSearch 연동
- `models.py`: 아카이브 관련 모델

### `api/llm/`

LLM 호출과 프롬프트 관리를 담당한다.

- `service.py`: OpenAI 호환 `/chat/completions` 엔드포인트 호출
- `registry.py`: LLM 관련 등록 지점
- `prompt/system.py`: 시스템 프롬프트 정의

### `api/mcp/`

MCP 서버/도구 관련 코드가 모여 있다.

- `registry.py`: MCP 서버와 도구 메타데이터 등록/조회
- `client.py`: MCP 클라이언트 로직
- `executor.py`: 도구 실행 흐름
- `tool_selector.py`: 도구 선택 로직
- `tool_adapter.py`: 내부 표현과 실행 계층 연결
- `cache.py`: MCP 캐시 처리
- `models.py`: MCP 관련 모델
- `errors.py`: MCP 예외 정의
- `local_tools.py`: 로컬 도구 구현

### `api/scheduled_tasks/`

정기 작업 스케줄링 영역이다.

- `__init__.py`: `BackgroundScheduler` 초기화와 시작
- `_registry.py`: 작업 탐색 및 등록
- `_lock.py`: Redis 기반 분산 락 실행
- `tasks/`: 일반 스케줄 작업 모음

### `api/html_templates/`

Flask 렌더링용 HTML 템플릿이다.

- `main.html`: 기본 페이지
- `monitor.html`: 모니터링 페이지
- `file_delivery.html`: 파일 전달 페이지

### `api/utils/`

공통 유틸리티 영역이다.

- `utils/logger/paths.py`: 로그 경로 계산
- `utils/logger/formatters.py`: 로그 포맷터 정의
- `utils/logger/service.py`: 로그 기록 서비스

### `api/workflows/`

워크플로우 기반 대화 처리 계층이다.

- `orchestrator.py`: 워크플로우 실행, resume, handoff, 종료 후 부모 복귀를 총괄한다.
- `registry.py`: 사용 가능한 워크플로우와 entry node를 등록한다.
- `state_service.py`: 사용자별 워크플로우 상태를 저장/복원한다.
- `models.py`: `WorkflowState`, `NodeResult` 등 공통 모델을 정의한다.

## 워크플로우 디렉터리

```text
api/workflows/
├── common/
├── start_chat/
├── chart_maker/
├── ppt_maker/
├── recipe_requests/
├── at_wafer_quota/
└── sample/
```

- `start_chat/`: 기본 진입 워크플로우
- `common/`: 공통 처리 흐름
- `chart_maker/`: 차트 생성 관련 흐름
- `ppt_maker/`: PPT 생성 관련 흐름
- `recipe_requests/`: 레시피 요청 처리 흐름
- `at_wafer_quota/`: 특정 도메인 질의 처리 흐름
- `sample/`: 예제 워크플로우

각 워크플로우는 대체로 아래 패턴을 따른다.

- `graph.py`: 노드 그래프 정의
- `nodes.py`: 실제 노드 처리 함수
- `routing.py`: 분기 규칙
- `state.py`: 워크플로우 전용 상태 정의
- `prompts.py`: 프롬프트 정의
- `agent/`, `rag/`: 필요 시 보조 실행기나 검색 계층

## 요약

`api/`는 Flask 엔트리, Cube 연동, 파일 전달, LLM 호출, MCP, 스케줄러, 워크플로우를 모두 품고 있는 핵심 계층이다. 이 프로젝트를 이해할 때는 `api/__init__.py`, `api/cube/`, `api/workflows/`, `api/config.py`를 먼저 보는 것이 가장 효율적이다.
