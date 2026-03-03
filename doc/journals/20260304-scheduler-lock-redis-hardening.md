## 1. 진행 사항
- `api/utils/scheduler.py`에 Redis 분산 락 기반 실행 제어를 추가해, 다중 uWSGI worker 환경에서도 동일 스케줄러 잡이 중복 실행되지 않도록 처리했다.
- APScheduler에 strict job control(`coalesce=True`, `max_instances=1`, `misfire_grace_time`)을 적용했다.
- 스케줄러 락 설정을 `api/config.py` 및 `.env.example`로 노출했다.
- 사용자 요청에 따라 스케줄러 락 prefix를 `scheduler:sknn_v3`로 반영했다.
- 신규 테스트 `tests/test_scheduler.py`를 작성하고 실행했다.
- 검증 명령:
  - `pytest tests/test_scheduler.py tests/test_index.py -v` (16 passed)
  - `pytest tests/test_scheduler.py -v` (4 passed)

## 2. 수정 내용
- 변경 파일:
  - `.env.example`
  - `api/config.py`
  - `api/utils/scheduler.py`
  - `tests/test_scheduler.py` (신규)
  - `MEMORY.md`
- 핵심 변경:
  - `api/config.py`:
    - `SCHEDULER_REDIS_URL`
    - `SCHEDULER_LOCK_PREFIX` (기본값: `scheduler:sknn_v3`)
    - `SCHEDULER_LOCK_TTL_SECONDS`
    - `SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS`
    - `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`
  - `api/utils/scheduler.py`:
    - `_RedisDistributedLock` 추가 (acquire/release + renew loop)
    - `_run_locked_job()` 추가 (잡 실행 시 Redis 락 획득 실패/미사용 시 스킵)
    - `_cleanup_uwsgi_logs_job()`로 실제 작업을 락 래핑
    - `BackgroundScheduler(job_defaults=...)` 및 `add_job(..., replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=...)` 적용
  - `tests/test_scheduler.py`:
    - 락 획득/해제 정상 동작
    - 락 선점 시 스킵
    - Redis 미가용 시 스킵
    - `start_scheduler()` strict defaults/idempotent 검증

## 3. 다음 단계
- 운영 환경에 `SCHEDULER_REDIS_URL`이 유효한지 확인하고, 필요 시 Redis secondary 주소로 폴백 정책을 확정한다.
- 실제 10분 이상 걸리는 잡에 대해 `SCHEDULER_LOCK_TTL_SECONDS`를 작업 최대 시간보다 충분히 크게 설정한다.
- 배포 후 로그에서 `Skipping scheduler job`/`lock already held` 메시지 비율을 모니터링해 락/스케줄 주기를 조정한다.

## 4. 메모리 업데이트
- `MEMORY.md`에 스케줄러 Redis 분산 락 규칙(`scheduler:sknn_v3` prefix, TTL/renew/misfire 설정, Redis 미가용 시 안전 스킵)을 추가했다.
