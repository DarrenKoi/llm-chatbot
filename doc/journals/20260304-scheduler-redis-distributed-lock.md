# 스케줄러 Redis 분산 락 구현 및 패키지 리팩토링

## 1. 진행 사항

### 세션 1: 설계 및 현황 점검
- Flask 앱 내 스케줄러 현황 점검: `api/__init__.py`, `api/utils/scheduler.py`, `api/config.py`, `api/routes.py`, `wsgi.ini`를 확인해 현재 `BackgroundScheduler`가 앱 초기화 시점에 시작되는 구조를 파악함.
- 테스트/의존성 점검: `requirements.txt`, `tests/test_index.py` 및 `rg` 검색으로 APScheduler/Redis 사용 범위와 스케줄러 테스트 부재를 확인함.
- APScheduler 기능 확인: `apscheduler 3.11.2` 및 `apscheduler.jobstores.redis.RedisJobStore` import 가능 여부를 검증함.
- uWSGI 멀티 워커 환경에서 중복 실행 방지를 위해 Redis 분산 락 기반 리더 선출(leader election) + failover 방식 계획 수립.

### 세션 2: Redis 분산 락 구현
- `api/utils/scheduler.py`에 Redis 분산 락 기반 실행 제어를 추가해, 다중 uWSGI worker 환경에서도 동일 스케줄러 잡이 중복 실행되지 않도록 처리.
- APScheduler에 strict job control(`coalesce=True`, `max_instances=1`, `misfire_grace_time`) 적용.
- 스케줄러 락 설정을 `api/config.py` 및 `.env.example`로 노출.
- 스케줄러 락 prefix를 `scheduler:sknn_v3`로 설정.
- `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS` 기본값을 `60`으로 낮춰 재시작 후 과거 잡 즉시 실행(catch-up) 최소화.
- `tests/test_scheduler.py` 신규 작성 (4 tests passed).

### 세션 3: 패키지 리팩토링
- `api/utils/scheduler.py` 단일 파일을 `api/utils/scheduler/` 패키지로 리팩토링.
- 토픽별 작업 파일 분리 구조 설계 및 구현.
- `pkgutil` 기반 자동 탐색(auto-discovery) 레지스트리 구현.
- 스케줄링 패턴 예제 파일 작성 (cron, interval, date 트리거).

## 2. 수정 내용

### 설정 파일
- `.env.example` — 스케줄러 관련 환경 변수 추가
- `api/config.py` — `SCHEDULER_REDIS_URL`, `SCHEDULER_LOCK_PREFIX`(`scheduler:sknn_v3`), `SCHEDULER_LOCK_TTL_SECONDS`, `SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS`, `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`(`60`)

### 패키지 구조 (최종)
- `api/utils/scheduler.py` 삭제 → `api/utils/scheduler/` 패키지로 전환:
  - `__init__.py` — `start_scheduler()`, `run_locked_job` 공개 API. 기존 import 경로 호환 유지
  - `_lock.py` — Redis 분산 락 인프라 (`_RedisDistributedLock`, Lua 스크립트, `run_locked_job()`, `_get_scheduler_redis_client()`)
  - `_registry.py` — `pkgutil.iter_modules`로 `tasks/` 하위 모듈 자동 탐색, `_` 접두사 모듈 스킵
  - `tasks/__init__.py` — 빈 패키지 init
  - `tasks/cleanup.py` — uWSGI 로그 정리 작업, `register()` 함수로 등록
  - `tasks/_examples.py` — 4가지 스케줄링 패턴 예제 + 트리거 레퍼런스

### 테스트
- `tests/test_scheduler.py` — 4개 테스트 (락 획득/해제, 락 선점 시 스킵, Redis 미가용 시 스킵, `start_scheduler()` strict defaults)

### 변경 없음
- `api/__init__.py` — `from api.utils.scheduler import start_scheduler` 그대로 동작

## 3. 다음 단계
- 운영 환경에 `SCHEDULER_REDIS_URL`이 유효한지 확인하고, 필요 시 Redis secondary 주소로 폴백 정책 확정.
- 실제 10분 이상 걸리는 잡에 대해 `SCHEDULER_LOCK_TTL_SECONDS`를 작업 최대 시간보다 충분히 크게 설정.
- 배포 후 로그에서 `Skipping scheduler job`/`lock already held` 메시지 비율을 모니터링해 락/스케줄 주기 조정.
- 실제 백그라운드 작업이 필요할 때 `tasks/` 하위에 토픽별 파일 추가 (예: `monitoring.py`, `reporting.py`).

## 4. 메모리 업데이트
- `MEMORY.md`에 스케줄러 Redis 분산 락 규칙 및 패키지 구조 반영 완료.
