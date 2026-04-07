# Supporting Files And Directories

이 문서는 `api/` 밖의 주요 파일과 보조 디렉터리 구조를 정리한다.

## 실행 관련 파일

- `index.py`: 로컬 개발용 Flask 앱 실행 파일
- `scheduler_worker.py`: APScheduler 전용 별도 프로세스 진입점
- `cube_worker.py`: Cube 큐 소비 워커 진입점
- `wsgi.ini`: uWSGI 실행 설정. `attach-daemon` 으로 `cube_worker.py`, `scheduler_worker.py`를 함께 띄우는 운영 구성을 담는다.
- `requirements.txt`: Python 의존성 목록
- `README.md`: 프로젝트 개요와 실행 방법

## `tests/`

`pytest` 기반 테스트 코드가 위치한다.

```text
tests/
├── conftest.py
├── test_cube_*.py
├── test_scheduler*.py
├── test_*workflow.py
├── test_llm_service.py
├── test_conversation_service.py
├── test_main_page.py
├── test_monitor_page.py
└── test_index.py
```

- `conftest.py`: 공통 fixture와 테스트 설정
- `test_cube_*`: Cube payload, router, service, worker 관련 테스트
- `test_scheduler*`: 스케줄러, cleanup task, 워커 테스트
- `test_*workflow.py`: 워크플로우 실행 흐름 테스트
- `test_main_page.py`, `test_monitor_page.py`, `test_index.py`: Flask 앱/페이지 테스트
- `test_logger_utils.py`, `test_router_loader.py`, `test_http_clients.py`: 공통 유틸/로더/클라이언트 테스트

## `doc/`

프로젝트 문서와 작업 기록이 저장된다.

- `프로젝트_개요.md`: 프로젝트 개요 문서
- `guideline/`: 라우터 가이드 등 개발 문서
- `journals/`: 날짜별 작업 로그
- `generate_slides.py`, `.pptx`: 문서/발표 자료 생성 관련 산출물

## `scripts/`

운영 또는 개발 보조 스크립트 디렉터리다.

- `check_tool_calling.py`: 도구 호출 동작 점검
- `sync_to_bitbucket.py`: 외부 저장소 동기화 보조

## 런타임 데이터 디렉터리

- `logs/`: 활동 로그 저장 위치
  - `logs/activity/`: 일자별 활동 로그 파일
- `var/`: 애플리케이션 런타임 상태 저장소
  - `var/mcp_cache/`: MCP 캐시 디렉터리

> 워크플로 상태는 LangGraph checkpointer(MongoDB)가 관리한다. 이전의 `var/workflow_state/` JSON 파일 방식은 폐기되었다.

## 추천 탐색 순서

1. `README.md`
2. `index.py`
3. `scheduler_worker.py` 또는 `cube_worker.py`
4. `tests/`에서 관련 테스트 확인
5. `doc/`에서 설계 문서와 작업 기록 확인

## 요약

이 프로젝트는 실행 진입점, 테스트, 문서, 스크립트, 런타임 데이터가 비교적 명확하게 분리되어 있다. 실제 애플리케이션 로직은 `api/`에 집중되어 있고, 나머지 디렉터리는 실행 보조, 검증, 운영 기록 성격이 강하다.
