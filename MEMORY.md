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
- `api/cube/service.py`는 LLM 응답이 `LLM_THINKING_MESSAGE_DELAY_SECONDS`를 초과할 때만 `LLM_THINKING_MESSAGE`를 전송한다.
- 현재 기본 `LLM_THINKING_MESSAGE_DELAY_SECONDS` 값은 `5`초다.

## Redis 사용 규칙
- Redis 기반 기능은 기본적으로 `REDIS_URL` 단일 설정을 사용한다.
- Cube 큐는 항상 `REDIS_URL`을 사용한다.
- `SCHEDULER_REDIS_URL`, `FILE_DELIVERY_REDIS_URL`이 비어 있으면 `REDIS_URL`을 기본값으로 사용한다.
- 현재 기본 Redis는 `10.156.133.126:10121`이다.

## 스케줄러 락 규칙
- 스케줄러 잡 실행(`api/scheduled_tasks/_lock.py`)은 Redis 분산 락을 사용한다.
- 락 키 접두사는 `SCHEDULER_LOCK_PREFIX`이며 기본값은 `scheduler:sknn_v3`이다.
- 락/잡 제어는 `SCHEDULER_LOCK_TTL_SECONDS`, `SCHEDULER_LOCK_RENEW_INTERVAL_SECONDS`, `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`로 조정한다.
- 현재 기본 `SCHEDULER_JOB_MISFIRE_GRACE_SECONDS`는 `60`으로, 서버 재기동 후 과거 스케줄 catch-up 실행을 최소화한다.
- Redis 잠금 백엔드가 없으면 안전을 위해 스케줄러 잡 실행을 스킵한다.
- 스케줄러는 `wsgi.ini`의 `attach-daemon = python scheduler_worker.py`로 전용 프로세스에서만 실행된다. 웹 앱은 스케줄러를 시작하지 않는다.

## uWSGI 재시작 정책
- `wsgi.ini`에서 `reload-mercy=15`, `worker-reload-mercy=15`으로 설정해 `touch-reload` 시 실행 중 작업에 짧은 정리 시간을 주고 재시작한다.
- 현재 기본 웹앱 동시성은 `workers=2`, `threads=4`이며, 별도 `cube_worker.py` / `scheduler_worker.py` daemon과 분리해 운영한다.

## 모니터링 규칙
- `/monitor`는 `REDIS_URL` ping 결과를 `Primary Redis` 항목으로 표시한다.
- `/monitor`의 daemon 상태는 activity log의 `*_worker_started`, `*_worker_heartbeat` 이벤트 시각으로 판별한다.
- `cube_worker.py`, `scheduler_worker.py`는 주기적으로 heartbeat 이벤트를 남겨 모니터링 페이지에서 running/stale/not running 상태를 계산할 수 있어야 한다.

## File Delivery 규칙
- 파일 전달 업로드/조회 엔드포인트:
  - `POST /api/v1/file-delivery/upload` (multipart/form-data)
  - `GET /file-delivery/files/<file_id>`
- 파일 전달 메타데이터 저장은 `FILE_DELIVERY_REDIS_URL`을 사용한다.
- 파일은 사용자별 폴더 전략을 고려하되, 외부 노출 식별자는 내부 경로가 아닌 `file_id` 기준으로 유지한다.
- 파일 보관 기간 기본값은 30일이며, 스케줄러가 만료 파일을 정리한다.
- Cube 대화창 자체에서는 사용자가 파일 업로드/다운로드를 직접 수행할 수 없다고 가정한다.
- 따라서 LLM이 파일 제출을 요청해야 할 때는 Cube 안에서 처리하지 말고, 사용자 전용 웹 업로드 페이지 URL을 안내하는 흐름으로 설계한다.

## 네트워크 제약
- 이 서비스와 Cube 연동은 사내망 전용이다.
- 외부 인터넷에서는 웹앱과 Cube 서비스에 접근할 수 없도록 방화벽으로 차단된 환경을 전제로 설계한다.
- 운영 접근 프로토콜은 HTTPS가 아니라 HTTP만 허용되는 환경을 전제로 한다.

## 로컬 Workflow 개발 규칙
- 로컬 개발 전용 UI와 실행기는 루트 `devtools/workflow_runner/`에 둔다.
- 로컬 초안 workflow는 `devtools/workflows/<workflow_id>/`에 작성하고, 패키지 구조와 계약은 `api/workflows/<workflow_id>/`와 동일하게 유지한다.
- 운영 반영 대상 workflow의 단일 기준 경로는 `api/workflows/`다.
- 로컬 개발 transcript/history는 production과 공유하지 않고 브라우저 로컬 저장소 기준으로 분리한다.
- 로컬 개발 workflow를 운영으로 올릴 때는 copy가 아니라 promotion(move 기준) 절차를 사용한다.

## MCP 도구 선택 규칙
- `WorkflowDefinition`은 선택적 `tool_tags` 필드를 가질 수 있고, 값은 소문자 태그 tuple로 정규화한다.
- `api/mcp_client/models.py`의 `MCPTool.tags`도 소문자 태그 tuple로 정규화한다.
- `api/mcp_client/tool_selector.py`는 workflow의 `tool_tags`와 MCP 도구의 `tags`를 매칭해 도구 후보를 필터링한다.
- `tool_tags`가 비어 있는 workflow는 기존처럼 전체 도구를 그대로 노출한다.

## LangGraph 저장 규칙
- LangGraph 체크포인트는 MongoDB `cube_checkpoints` / `cube_checkpoint_writes` 컬렉션을 사용하며 기본 TTL은 3일(`CHECKPOINT_TTL_SECONDS=259200`)이다.
- 대화 이력 보관용 컬렉션은 `cube_conversation_history`를 기본값으로 사용하고, 기본 TTL 없이 영구 보관한다(`CONVERSATION_TTL_SECONDS=0`).
- 체크포인트는 단기 실행 상태와 resume 용도, 대화 이력 컬렉션은 감사/모니터링/장기 조회 용도로 분리한다.

## Workflow 결정 패턴
- `translator`와 `travel_planner` 계열 워크플로는 규칙 기반 슬롯 파싱 대신 LLM 결정 레이어를 우선 사용한다.
- LLM 결정 레이어는 `api/llm/service.py`의 `generate_json_reply()`를 통해 현재 `LLM_MODEL`로 JSON 액션을 반환받는다.
- 워크플로 노드는 LLM이 판단한 `action`만 해석하고, 실제 실행(번역 도구 호출, 추천 문구 생성, 계획 생성)은 결정적 코드 경로로 유지한다.
- LLM 호출 실패나 JSON 파싱 실패 시에는 워크플로 전용 fallback 규칙으로 안전하게 복구한다.
- devtools 예제 워크플로도 production과 동일한 LLM 결정 모듈을 재사용해 흐름 차이를 최소화한다.
