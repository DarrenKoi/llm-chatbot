# 진행 사항
- `api/config.py`에서 `REDIS_FALLBACK_URL`을 제거하고 Redis 기본 선택을 `REDIS_URL` 단일 설정으로 정리했다.
- Cube 큐가 별도 Redis URL을 받지 않고 항상 primary Redis를 사용하도록 `api/config.py`, `api/cube/queue.py`, `api/monitoring_service.py`를 수정했다.
- 예제 환경 파일 `.env.example`에서 `REDIS_FALLBACK_URL`, `CUBE_QUEUE_REDIS_URL` 항목을 제거했다.
- `tests/test_config.py`에 `REDIS_URL` 기본 사용, `REDIS_FALLBACK_URL` 무시, `CUBE_QUEUE_REDIS_URL` 무시 동작을 검증하는 테스트를 추가했다.
- `pytest tests/test_config.py tests/test_cube_worker.py tests/test_cube_service.py tests/test_cube_router.py -v`를 실행해 관련 회귀를 확인했다.

# 수정 내용
- 변경 파일: `api/config.py`
  - `REDIS_FALLBACK_URL` 선언 제거
  - `CUBE_QUEUE_REDIS_URL = REDIS_URL`로 고정
  - `SCHEDULER_REDIS_URL`, `FILE_DELIVERY_REDIS_URL` 기본값을 `REDIS_URL`로 유지
- 변경 파일: `api/cube/queue.py`
  - Cube 큐 Redis 미설정 오류 메시지를 `REDIS_URL` 기준으로 수정
- 변경 파일: `api/monitoring_service.py`
  - Cube Queue 헬스체크가 `REDIS_URL`을 직접 보도록 수정
  - 미설정 안내 문구를 `REDIS_URL` 기준으로 수정
- 변경 파일: `tests/test_config.py`
  - 단일 Redis 기본값 테스트 추가/정리
  - `REDIS_FALLBACK_URL` 및 `CUBE_QUEUE_REDIS_URL` 환경변수가 무시되는지 검증 추가
- 변경 파일: `.env.example`
  - fallback/queue 전용 Redis 예시 변수 제거
- 변경 파일: `MEMORY.md`
  - Redis 운영 규칙을 단일 `REDIS_URL` 기준으로 업데이트

# 다음 단계
- 배포 환경 변수에서 `REDIS_FALLBACK_URL`과 `CUBE_QUEUE_REDIS_URL`가 남아 있으면 제거한다.
- `REDIS_URL`이 primary Redis를 가리키는지 확인한 뒤 재배포한다.
- 재배포 후 Cube webhook 수신과 worker 소비가 같은 Redis를 보는지 모니터링에서 확인한다.

# 메모리 업데이트
- `MEMORY.md`의 Redis 사용 규칙을 단일 `REDIS_URL` 기준으로 수정했다.
