# Cube 비동기 큐 전환 및 200 ACK 처리

**날짜**: 2026-03-19  
**이슈 주제**: Cube webhook 요청이 LLM 응답 완료까지 동기 처리되어 대기 안내 문구 반복 및 retry 가능성이 있던 문제를 Redis 큐 + 별도 worker 구조로 전환

---

## 1. 원인 추정

- 기존 `/api/v1/cube/receiver`는 요청을 받은 뒤 같은 HTTP 요청 안에서 아래 작업을 모두 처리했다.
  - 대화 이력 조회/저장
  - LLM 응답 생성
  - Cube `multiMessage` 재전송
- 이 구조에서는 Cube가 webhook ACK를 늦게 받기 때문에 플랫폼 쪽에서 `잠시 대기 중입니다`류의 안내 문구를 반복 노출하거나 같은 메시지를 재전송할 가능성이 있다.
- 기존 코드에는 `message_id="-1"` + `!@#` prefix wake-up 이벤트를 무시하는 로직이 이미 있었기 때문에, 실제 운영에서도 idle/wakeup 성격의 Cube 이벤트가 들어오는 상황으로 보였다.
- `message_id` 기반 중복 방지가 없어서 동일 요청 retry 시 같은 메시지를 다시 처리할 수 있었다.

## 2. 이번 변경

### 요청 처리 구조

- `api/cube/router.py`
  - Cube receiver는 payload 검증 및 enqueue만 수행
  - 큐 적재 결과를 `200 OK`로 즉시 반환
  - 반환 status는 `accepted`, `duplicate`, `ignored`

### 서비스 계층

- `api/cube/service.py`
  - `accept_cube_message()` 추가
  - wake-up 메시지는 enqueue 없이 `ignored` 처리
  - Redis 큐 장애는 `CubeQueueUnavailableError(503)`로 분리
  - 기존 LLM 처리 경로는 `process_incoming_message()` / `process_queued_message()`로 분리

### Redis 큐

- `api/cube/queue.py` 신규
  - Redis 기반 ready queue / processing queue 추가
  - Lua script로 `message_id` dedupe + enqueue를 원자적으로 수행
  - worker 재시작 시 processing queue의 stranded item을 ready queue로 복구 가능

### Worker

- `api/cube/worker.py` 신규
  - Redis에서 메시지를 꺼내 LLM 호출 및 Cube 응답 전송 수행
  - 실패 시 retry 횟수 내에서 재큐잉
  - 최대 retry 초과 시 로그를 남기고 drop
- `cube_worker.py` 신규
  - 운영 실행용 진입점

### 설정

- `api/config.py`, `.env.example`
  - `CUBE_QUEUE_REDIS_URL`
  - `CUBE_QUEUE_NAME`
  - `CUBE_QUEUE_PROCESSING_NAME`
  - `CUBE_MESSAGE_DEDUP_TTL_SECONDS`
  - `CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS`
  - `CUBE_QUEUE_MAX_RETRIES`
  - `CUBE_WORKER_RETRY_DELAY_SECONDS`

### 테스트

- `tests/test_cube_router.py`
  - 200 ACK, duplicate, queue failure 케이스 반영
- `tests/test_cube_service.py`
  - enqueue/duplicate/wakeup/동기 처리 예외 경로 반영
- `tests/test_cube_worker.py`
  - worker 성공, retry, max retry 초과 케이스 추가
- `tests/test_main_page.py`
  - 현재 템플릿 문구 기준으로 stale assertion 정리

## 3. 코드 변경 상세

### `api/cube/router.py`

- `receive_cube()`의 처리 대상을 `handle_cube_message()`에서 `accept_cube_message()`로 변경
- 정상 응답 코드를 `202`에서 `200`으로 변경
- 응답 JSON을 worker 처리 상태에 맞춰 `{"status": ..., "message_id": ...}` 형태로 유지

### `api/cube/service.py`

- `accept_cube_message(payload)`
  - payload를 파싱한 뒤 wake-up 메시지는 `ignored`로 즉시 종료
  - 일반 메시지는 `enqueue_incoming_message()`를 호출해 Redis 큐에 적재
  - dedupe로 enqueue되지 않은 경우 `duplicate` status 반환
  - Redis 장애 시 `CubeQueueUnavailableError(503)`로 변환
- `process_incoming_message(incoming, attempt=0)`
  - 기존 `handle_cube_message()`의 실제 LLM 처리 본문을 분리
  - queue attempt를 activity/log_request에 같이 남기도록 확장
- `process_queued_message(queued_message)`
  - worker가 `CubeQueuedMessage`를 직접 처리할 수 있게 추가
- `handle_cube_message(payload)`
  - 기존 테스트/호환성을 위해 유지하되, 내부적으로는 `process_incoming_message()`를 호출하는 thin wrapper로 축소

### `api/cube/queue.py`

- `enqueue_incoming_message(incoming)`
  - Redis Lua script로 dedupe key 등록과 queue push를 원자적으로 처리
  - dedupe key 형식: `cube:incoming:dedup:{user_id}:{message_id}`
- `dequeue_queued_message(timeout_seconds=None)`
  - ready queue에서 processing queue로 메시지를 reserve
- `acknowledge_queued_message(queued_message)`
  - processing queue에서 처리 완료 메시지 제거
- `requeue_queued_message(queued_message, next_attempt=...)`
  - 실패 메시지를 processing queue에서 빼고 retry attempt를 증가시켜 ready queue에 재적재
- `recover_processing_messages()`
  - worker 재시작 시 processing queue에 남은 stranded item을 ready queue로 복구
- queue payload 형식
  - `{"incoming": {...CubeIncomingMessage...}, "attempt": <int>}`

### `api/cube/worker.py`

- `process_next_queued_message()`
  - Redis queue에서 1건을 가져와 `process_queued_message()` 실행
  - 성공 시 acknowledge
  - 실패 시 `CUBE_QUEUE_MAX_RETRIES` 범위 내에서 requeue
  - retry 초과 시 acknowledge 후 error log만 남기고 drop
- `run_worker(once=False)`
  - 시작 시 `recover_processing_messages()` 수행
  - 이후 block timeout 기반으로 계속 polling
- `main(argv=None)`
  - `--once` 옵션을 지원하는 CLI entrypoint 추가

### `api/cube/models.py`

- `CubeAcceptedMessage`
  - receiver 단계 응답 상태를 표현하기 위해 추가
- `CubeQueuedMessage`
  - worker queue payload와 retry attempt를 표현하기 위해 추가

### `api/config.py` / `.env.example`

- Cube async queue 관련 환경변수 추가
  - `CUBE_QUEUE_REDIS_URL`
  - `CUBE_QUEUE_NAME`
  - `CUBE_QUEUE_PROCESSING_NAME`
  - `CUBE_MESSAGE_DEDUP_TTL_SECONDS`
  - `CUBE_QUEUE_BLOCK_TIMEOUT_SECONDS`
  - `CUBE_QUEUE_MAX_RETRIES`
  - `CUBE_WORKER_RETRY_DELAY_SECONDS`

### `cube_worker.py`

- 운영에서 worker를 독립 실행할 수 있도록 루트 실행 파일 추가

## 4. 운영 메모

- 웹 프로세스는 빠르게 `200 OK`만 반환하고, 실제 응답은 worker가 Cube로 push한다.
- 운영에서는 웹 서버와 별도로 worker 프로세스를 같이 띄워야 한다.
  - 예시: `python cube_worker.py`
  - 예시: `python -m api.cube.worker`
- Redis가 내려가면 receiver는 `503`을 반환하므로, 이 경우 Cube 쪽 retry가 발생할 수 있다.
- `message_id`가 없는 요청은 dedupe를 적용하지 않는다.

## 5. Git 복구 시점

- 변경 직전 복구 기준 HEAD:
  - `e00b19b0ebd0baa33bda79a8c96d39782f48cbe1`
- 문제 발생 시 이 시점으로 되돌릴 수 있다.
  - `git reset --hard e00b19b0ebd0baa33bda79a8c96d39782f48cbe1`

## 6. 검증

- `python -m pytest tests -v`
  - 45 passed
