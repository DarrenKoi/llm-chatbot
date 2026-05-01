# 사내 개발 환경 정리

이 문서는 현재 저장소 곳곳에 흩어져 있는 사내 개발 환경 정보를 한곳에 모아 정리한 메모다.
실제 비밀값은 포함하지 않았고, URL·호스트·경로·기본값 중심으로만 요약했다.

## 1. 한 줄 요약

- 집에서는 코드 작성과 mock 기반 테스트를 진행한다.
- Cube 연동 확인과 사내망 기반 통합 검증은 사무실 환경에서 수행한다.
- 운영/검증 환경은 사내망 전용이며 외부 인터넷에서 직접 접근할 수 없다고 가정한다.

## 2. 네트워크와 접근 제약

- Cube와 이 웹앱은 사내망 전용 환경을 전제로 한다.
- 외부 인터넷에서는 웹앱과 Cube 서비스에 접근할 수 없도록 방화벽으로 차단된 환경을 가정한다.
- 운영 접근은 HTTPS가 아니라 HTTP 중심 환경을 전제로 한다.
- `CLAUDE.md` 기준으로, 집에서는 Cube 접근이 불가능하고 사무실에서 통합 테스트를 수행한다.

## 3. 런타임 기본 프로필

- 기본 Python 버전은 `3.11`이다.
- 로컬 개발 서버 포트는 `5000`이다.
- Flask 앱 기본 이름은 `llm_chatbot`, 기본 환경값은 `development`다.
- 기본 타임존은 LLM/로그 모두 `Asia/Seoul`이다.
- Linux에서 `/project/workSpace`가 존재하면 이를 기본 workspace root로 사용한다.

## 4. 사내 기본 엔드포인트와 경로

### Cube

- 기본 Cube API URL: `http://cube.skhynix.com:8888`
- 멀티메시지 URL: `http://cube.skhynix.com:8888/api/multiMessage`
- Rich Notification URL: `http://cube.skhynix.com:8888/legacy/richnotification`
- 기본 봇 이름: `ITC OSS`

### 웹앱 / 파일 전달

- 기본 웹앱 URL: `http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com`
- 파일 전달 저장 경로: `/project/workSpace/itc-1stop-solution-pjt-shared/file_delivery`
- 파일 전달 기본 URL: `{WEB_APP_URL}/file-delivery/files`
- Linux 배포 환경의 touch reload 파일: `/project/workSpace/restart.txt`

### 내부 MCP 예시 엔드포인트

- Dev endpoint: `http://itc-1stop-solution-mcp-basic-dev.api.hcpnd01.skhynix.com`
- Prd endpoint: `http://itc-1stop-solution-mcp-basic-prd.api.hcpp01.skhynix.com`
- 서버 ID 예시: `ITC_OSS_MCP`

## 5. 저장소와 백엔드 사용 방식

### Redis

- Redis 기반 기능은 기본적으로 `REDIS_URL` 하나를 중심으로 동작한다.
- Cube 큐는 항상 `REDIS_URL`을 사용한다.
- `SCHEDULER_REDIS_URL`, `FILE_DELIVERY_REDIS_URL`, `USER_PROFILE_REDIS_URL`이 비어 있으면 `REDIS_URL`을 기본값으로 사용한다.
- 현재 메모와 예시 설정 기준 기본 Redis 호스트는 `10.156.133.126:10121`이다.
- 이 문서에는 비밀번호를 적지 않는다. 실제 인증 정보는 `.env` 또는 별도 비밀 저장소에서 관리해야 한다.

### MongoDB

- `AFM_MONGO_URI`가 설정되면 대화 이력과 LangGraph 체크포인트를 MongoDB에 저장한다.
- `.env.example`에는 Mongo URI가 비어 있어, 비밀정보는 예시 파일에 넣지 않는 방식이다.
- 기본 DB 이름은 `itc-afm-data-platform-mongodb`다.
- 기본 컬렉션 이름:
  - `cube_conversation_history`
  - `cube_checkpoints`
  - `cube_checkpoint_writes`
- LangGraph 체크포인트 TTL 기본값은 `259200`초, 즉 3일이다.
- 대화 이력 TTL 기본값은 `0`으로 영구 보관 기준이다.

## 6. 프로세스 구성

- 웹앱은 uWSGI 기준 `workers=2`, `threads=4`로 운영한다.
- `wsgi.ini`는 아래 두 개의 전용 daemon을 함께 붙인다.
  - `python cube_worker.py`
  - `python scheduler_worker.py`
- 스케줄러는 웹앱 프로세스가 아니라 전용 `scheduler_worker.py` 프로세스에서만 실행한다.
- `touch-reload`는 `/project/workSpace/restart.txt` 파일 갱신으로 수행한다.

## 7. 사무실 기준 검증 포인트

- 사내망에서 Cube webhook 수신이 가능한지 확인한다.
- Redis 연결과 Cube queue round-trip 이 정상인지 확인한다.
- 필요 시 MongoDB 연결과 컬렉션 구성이 맞는지 확인한다.
- 파일 전달 URL이 사내망에서 열리고, 저장 경로 권한이 올바른지 확인한다.
- `cube_worker.py`, `scheduler_worker.py` heartbeat 가 모니터링 화면에서 정상 표시되는지 확인한다.

## 8. 집 개발 환경과의 역할 분리

- 집에서는 Cube 없이 개발한다.
- 집에서는 `pytest tests/ -v` 같은 mock 기반 테스트를 우선 사용한다.
- 새 workflow 초안은 `devtools/` 아래에서 브라우저 runner 로 검증할 수 있다.
- 실제 사내 연동 검증은 사무실 환경에서 별도로 확인해야 한다.

## 9. 자주 쓰는 명령

```bash
pip install -r requirements.txt
python index.py
pytest tests/ -v
uwsgi --ini wsgi.ini
python cube_worker.py
python scheduler_worker.py
```

## 10. 보안 메모

- `.env`는 로컬/사내 비밀값 보관용이며 절대 커밋하지 않는다.
- `.env.example`은 구조와 기본값 예시만 두고, 실제 토큰·비밀번호는 문서화하지 않는다.
- 이 문서는 사내 개발 환경의 구조를 요약한 문서이며, 비밀값 원문을 복사한 문서가 아니다.

## 11. 출처

- `CLAUDE.md`
- `MEMORY.md`
- `api/config.py`
- `.env.example`
- `wsgi.ini`
- `README.md`
