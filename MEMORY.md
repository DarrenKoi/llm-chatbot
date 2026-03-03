# MEMORY

## 런타임 기준
- 프로젝트 기본 파이썬 버전은 3.11이다.
- 관련 파일: `.python-version`(`3.11`), `runtime.txt`(`python-3.11.11`).

## 환경 설정 로딩 규칙
- `api/config.py`는 `.env`를 우선 로드하고, 없으면 `.env.example`을 로드한다.
- 경로 처리는 `pathlib.Path`를 사용한다.

## Redis 사용 규칙
- 대화 이력 저장(`api/services/conversation_service.py`)은 `REDIS_URL`(primary) -> `REDIS_FALLBACK_URL`(secondary) 순으로 연결을 시도한다.
- 둘 다 실패하면 in-memory 백엔드로 폴백한다.
- 현재 기본 우선 Redis는 `10.156.133.126:10121`이다.

## 스케줄러 락 규칙
- 스케줄러 잡 실행(`api/utils/scheduler.py`)은 Redis 분산 락을 사용한다.
- 락 키 접두사는 `SCHEDULER_LOCK_PREFIX`이며 기본값은 `scheduler:sknn_v3`이다.
- 락/잡 제어는 `SCHEDULER_LOCK_TTL_SECONDS`, `SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS`, `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`로 조정한다.
- 현재 기본 `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`는 `60`으로, 서버 재기동 후 과거 스케줄 catch-up 실행을 최소화한다.
- Redis 잠금 백엔드가 없으면 안전을 위해 스케줄러 잡 실행을 스킵한다.

## CDN 규칙
- CDN 업로드/조회 엔드포인트:
  - `POST /api/v1/cdn/upload` (multipart/form-data)
  - `GET /cdn/images/<image_id>`
- CDN 메타데이터 저장은 `CDN_REDIS_URL`을 사용한다(현재 `10.156.133.126:10121`).
- Linux 배포 기본 PVC 루트는 `/project/workSpace/pvc/download`이고, 기본 CDN 저장 경로는 `/project/workSpace/pvc/download/cdn/images`이다.
