### 1. 진행 사항
- Flask 앱 내 스케줄러 현황 점검: `api/__init__.py`, `api/utils/scheduler.py`, `api/config.py`, `api/routes.py`, `wsgi.ini`를 확인해 현재 `BackgroundScheduler`가 앱 초기화 시점에 시작되는 구조를 파악함.
- 테스트/의존성 점검: `requirements.txt`, `tests/test_index.py` 및 `rg` 검색으로 APScheduler/Redis 사용 범위와 스케줄러 테스트 부재를 확인함.
- APScheduler 기능 확인: `python3`로 `apscheduler 3.11.2` 및 `apscheduler.jobstores.redis.RedisJobStore` import 가능 여부를 검증함.
- 제안 아키텍처 정리: uWSGI 멀티 워커 환경에서 중복 실행 방지를 위해 Redis 분산 락 기반 리더 선출(leader election) + failover 방식 계획을 수립함.

### 2. 수정 내용
- 신규 파일 생성:
  - `doc/journals/20260304-apscheduler-redis-plan.md`
- 코드 파일 수정 없음 (설계/계획 정리 단계).

### 3. 다음 단계
- `api/config.py`에 스케줄러 환경 변수 추가: `SCHEDULER_ENABLED`, `SCHEDULER_REDIS_URL`, 락 키/TTL/갱신 주기, 타임존, 워커 수 등.
- `api/utils/scheduler.py`를 Redis 락 기반 단일 리더 실행 구조로 리팩터링하고, 리더 락 갱신/상실 처리 및 안전 종료 로직 추가.
- `api/__init__.py`에서 앱 생명주기와 스케줄러 시작/종료 훅을 정리해 웹 요청 처리와 독립적으로 동작하도록 보강.
- 스케줄러 동작 테스트 추가 후 `pytest tests/ -v`로 회귀 검증.

### 4. 메모리 업데이트
- 변경 없음
