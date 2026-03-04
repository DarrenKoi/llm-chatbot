# 스케줄러 패키지 리팩토링

## 진행 사항

- `api/utils/scheduler.py` 단일 파일을 `api/utils/scheduler/` 패키지로 리팩토링
- 토픽별 작업 파일 분리 구조 설계 및 구현
- `pkgutil` 기반 자동 탐색(auto-discovery) 레지스트리 구현
- 스케줄링 패턴 예제 파일 작성 (cron, interval, date 트리거)

## 수정 내용

### 삭제
- `api/utils/scheduler.py` — 기존 단일 파일 삭제

### 신규 생성
- `api/utils/scheduler/__init__.py` — `start_scheduler()`, `run_locked_job` 공개 API. 기존 import 경로 (`from api.utils.scheduler import start_scheduler`) 호환 유지
- `api/utils/scheduler/_lock.py` — Redis 분산 락 인프라 (`_RedisDistributedLock`, Lua 스크립트, `run_locked_job()`, `_get_scheduler_redis_client()`)
- `api/utils/scheduler/_registry.py` — `pkgutil.iter_modules`로 `tasks/` 하위 모듈 자동 탐색, 각 모듈의 `register(scheduler)` 호출. `_` 접두사 모듈은 스킵
- `api/utils/scheduler/tasks/__init__.py` — 빈 패키지 init
- `api/utils/scheduler/tasks/cleanup.py` — uWSGI 로그 정리 작업 (기존 로직 이동), `register()` 함수로 작업 등록
- `api/utils/scheduler/tasks/_examples.py` — 4가지 스케줄링 패턴 예제 (daily cron, weekly cron, interval, lock 없는 interval) + 트리거 레퍼런스

### 수정
- `tests/test_scheduler.py` — import 경로를 새 패키지 구조에 맞게 변경 (`lock_mod`, `scheduler_pkg`). 기존 4개 테스트 모두 유지 및 통과

### 변경 없음
- `api/__init__.py` — `from api.utils.scheduler import start_scheduler` 그대로 동작

## 다음 단계

- 실제 백그라운드 작업이 필요할 때 `tasks/` 하위에 토픽별 파일 추가 (예: `monitoring.py`, `reporting.py`)
- 필요 시 `_examples.py`에서 적절한 패턴 복사하여 사용

## 메모리 업데이트

스케줄러 패키지 구조 변경사항을 MEMORY.md에 반영.
