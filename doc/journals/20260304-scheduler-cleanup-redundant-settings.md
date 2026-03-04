# 스케줄러 중복 설정 정리

## 진행 사항

- `api/utils/scheduler/` 패키지 전체 코드 리뷰 수행
- 중복 설정 식별: `max_instances`, `coalesce`, `misfire_grace_time`가 scheduler `job_defaults`와 per-job 양쪽에 동일하게 설정되어 있음
- `_normalize_positive` 유틸리티 함수 불필요 판단 (음수 설정값 입력 가능성 없음)
- 중복 코드 제거 및 테스트 수정 후 전체 테스트 통과 확인 (37 passed)

## 수정 내용

### `api/utils/scheduler/_lock.py`
- `_normalize_positive()` 함수 삭제
- `_RedisDistributedLock.__init__`에서 `_normalize_positive(ttl_seconds, 3600)` → `ttl_seconds` 직접 사용

### `api/utils/scheduler/__init__.py`
- `_normalize_positive` import 제거
- `misfire_grace_time` 설정에서 `_normalize_positive()` 래핑 제거, `config.SCHEDULER_JOB_MISFIRE_GRACE_SECONDS` 직접 사용

### `api/utils/scheduler/_registry.py`
- `_normalize_positive` import 제거
- `config` import 제거 (더 이상 사용하지 않음)
- `_register_decorated_jobs()`에서 per-job `max_instances`, `coalesce`, `misfire_grace_time` 제거 — scheduler `job_defaults`에서 일괄 적용

### `tests/test_scheduler.py`
- `test_start_scheduler_uses_strict_job_defaults`: per-job kwargs에 `max_instances`, `coalesce`, `misfire_grace_time`가 없는지 확인하도록 변경
- `test_discover_and_register_supports_scheduled_job_decorator`: 동일하게 per-job kwargs 부재 확인으로 변경, 불필요한 `config` monkeypatch 제거

## 다음 단계

- 현재 추가 작업 없음. 스케줄러 관련 새 작업이 필요하면 별도 요청.

## 메모리 업데이트

- 변경 없음
