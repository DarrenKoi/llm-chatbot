# MEMORY

## 런타임 기준
- 프로젝트 기본 파이썬 버전은 3.11이다.
- 관련 파일: `.python-version`(`3.11`), `runtime.txt`(`python-3.11.11`).
- 로컬 개발 서버 포트는 고정 `5000`이다.

## 환경 설정 로딩 규칙
- `api/config.py`는 `.env`를 우선 로드하고, 없으면 `.env.example`을 로드한다.
- 경로 처리는 `pathlib.Path`를 사용한다.

## Cube 수신 처리 규칙
- `api/cube/router.py`는 Cube 웹훅 메시지를 수신해 대화 이력에 사용자 메시지만 저장한다.
- Tool calling 및 응답 생성은 별도 저장소에서 처리한다.

## Redis 사용 규칙
- 대화 이력 저장(`api/conversation_service.py`)은 `REDIS_URL`(primary) -> `REDIS_FALLBACK_URL`(secondary) 순으로 연결을 시도한다.
- 둘 다 실패하면 in-memory 백엔드로 폴백한다.
- 현재 기본 우선 Redis는 `10.156.133.126:10121`이다.

## 스케줄러 락 규칙
- 스케줄러 잡 실행(`api/utils/scheduler.py`)은 Redis 분산 락을 사용한다.
- 락 키 접두사는 `SCHEDULER_LOCK_PREFIX`이며 기본값은 `scheduler:sknn_v3`이다.
- 락/잡 제어는 `SCHEDULER_LOCK_TTL_SECONDS`, `SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS`, `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`로 조정한다.
- 현재 기본 `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`는 `60`으로, 서버 재기동 후 과거 스케줄 catch-up 실행을 최소화한다.
- Redis 잠금 백엔드가 없으면 안전을 위해 스케줄러 잡 실행을 스킵한다.
- 운영에서는 `wsgi.ini`의 `attach-daemon = python scheduler_worker.py`가 APScheduler 전용 프로세스를 담당하므로, 웹 앱 환경 변수 `APP_START_SCHEDULER`는 `false`로 유지한다.

## uWSGI 재시작 정책
- `wsgi.ini`에서 `reload-mercy=0`, `worker-reload-mercy=0`으로 설정해 `touch-reload` 시 실행 중 스케줄러 잡을 즉시 종료하고 빠르게 재시작한다.
- 현재 기본 웹앱 동시성은 `workers=2`, `threads=4`이며, 별도 `cube_worker.py` / `scheduler_worker.py` daemon과 분리해 운영한다.

## File Delivery 규칙
- 파일 전달 업로드/조회 엔드포인트:
  - `POST /api/v1/file-delivery/upload` (multipart/form-data)
  - `GET /file-delivery/files/<file_id>`
- 파일 전달 메타데이터 저장은 `FILE_DELIVERY_REDIS_URL`을 사용한다.
- 파일은 사용자별 폴더 전략을 고려하되, 외부 노출 식별자는 내부 경로가 아닌 `file_id` 기준으로 유지한다.
- 파일 보관 기간 기본값은 30일이며, 스케줄러가 만료 파일을 정리한다.

## 네트워크 제약
- 이 서비스와 Cube 연동은 사내망 전용이다.
- 외부 인터넷에서는 웹앱과 Cube 서비스에 접근할 수 없도록 방화벽으로 차단된 환경을 전제로 설계한다.
- 운영 접근 프로토콜은 HTTPS가 아니라 HTTP만 허용되는 환경을 전제로 한다.
