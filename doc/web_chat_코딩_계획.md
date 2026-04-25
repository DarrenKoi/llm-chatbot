# Cube 장애 대비 Nuxt 웹 채팅 코딩 계획

이 문서는 [`web_chat_확장_전략.md`](./web_chat_확장_전략.md)의 후속편으로, 실제 구현을 위한 단계별 작업 계획을 정리합니다. "왜"는 전략 문서가 책임지고, 본 문서는 "무엇을 어떤 순서로 만들 것인가"에 집중합니다.

## 0. 롤백 베이스라인

작업 시작 시점의 저장소 상태입니다. 결과가 만족스럽지 않을 경우 이 지점으로 되돌립니다.

- **Branch**: `main`
- **HEAD commit**: `ac3e88abf77ab3ccc09308f257b5f42063b202f8` (`ac3e88a`)
- **Commit message**: `scripts: Bitbucket 동기화 경로 인자 제거`
- **Recorded at**: 2026-04-26
- **Working tree**: dirty (`.claude/settings.local.json`, `api/llm/service.py`, `api/mcp/executor.py` 변경 / `nuxt-ui-llm.md` 미추적)
- **권장**: 작업 시작 전 미커밋 변경을 stash 또는 commit하여 깨끗한 상태에서 출발합니다.

**롤백 명령**

```bash
git reset --hard ac3e88abf77ab3ccc09308f257b5f42063b202f8
```

미커밋 변경을 잃을 수 있으므로 실행 전 반드시 확인합니다.

## 1. 목적과 범위

전략 문서가 정한 방향(같은 origin Flask serving, `ssr: false` SPA, `LASTUSER` cookie 인증, 같은 LangGraph thread 재사용)을 그대로 따라 구현합니다. 신규 챗봇을 만드는 것이 아니라 기존 `conversation_service`와 LangGraph checkpoint를 웹 채널에서도 재사용합니다.

## 2. 사전 확인 사항

- `AFM_MONGO_URI`가 운영에서 설정되는지 (홈 dev에서는 없어도 됨, §10 참조)
- 사내 SSO가 `/chat`과 `/api/v1/web-chat`까지 `LASTUSER` cookie를 전달하는지 (사무실 검증 필요)
- 운영에서 `/chat`과 `/api/v1/web-chat`이 같은 origin인지

## 3. 코드 탐색 결과 (구현 시 참조)

| 영역 | 파일 / 라인 | 메모 |
|------|-------------|------|
| Blueprint 자동 등록 | `api/blueprint_loader.py:11-24,40-46,66-82` | `router.py`의 `bp` / `blueprint` / `router` / `router_bp` 자동 검색 |
| Cube 진입 파이프라인 | `api/cube/service.py:277-465` | save → workflow → save → Cube 송신. 마지막 단계만 빼고 재사용 |
| Cube 메시지 모델 | `api/cube/models.py:5-10` | `CubeIncomingMessage` (frozen dataclass, 5필드) |
| 워크플로우 진입 | `api/workflows/lg_orchestrator.py:164` | `handle_message(incoming, attempt=0) -> WorkflowReply` |
| Thread ID 생성 | `api/workflows/langgraph_checkpoint.py:17-22` | `build_thread_id(user_id, channel_id) -> "user::channel"` |
| 대화 저장 | `api/conversation_service.py:63-86` | `append_message`, `append_messages`, `get_history` 존재. 사용자별 conversation 목록 조회는 없음 (Step 7에서 추가) |
| LASTUSER 사용 예 | `api/file_delivery/router.py:30-31` | `request.cookies.get("LASTUSER", "").strip()` 패턴 이미 존재 |
| Flask app 팩토리 | `api/__init__.py:17-107` | 정적 SPA serving 라우트 없음 (Step 12에서 추가). `discover_blueprints` 자동 호출 |
| 테스트 fixture | `tests/conftest.py:10-42` | `app`, `client`, `file_delivery_env` 사용 가능 |

**전략 문서와의 차이 (주의)**

1. 전략 문서 §8은 `handle_workflow_message`라고 적었지만 실제 함수명은 `api/workflows/lg_orchestrator.py:164`의 **`handle_message()`** 입니다. `api/cube/service.py:16`에서 별칭으로 import 하고 있을 뿐입니다.
2. 사용자별 conversation 목록 조회 함수는 `conversation_service`에 아직 없습니다. Step 7에서 신규 추가가 필요합니다.

## 4. 단계별 작업 순서

### Step 1. backend skeleton
- 파일 생성: `api/web_chat/__init__.py`, `models.py`, `identity.py`, `service.py`, `router.py`
- `router.py`: `bp = Blueprint("web_chat", __name__, url_prefix="/api/v1/web-chat")` (자동 등록)
- 다른 파일은 빈 함수 시그니처만 선언

### Step 2. identity 헬퍼
- `identity.py`: `get_current_web_chat_user() -> WebChatUser`
- `LASTUSER` cookie 없거나 빈 문자열이면 `werkzeug.exceptions.Unauthorized`
- `api/file_delivery/router.py:30-31` 패턴 그대로 차용
- 브라우저가 보낸 body의 `user_id`는 절대 사용하지 않음

### Step 3. DTO 모델
- `models.py`: `WebChatUser`, `WebChatMessageRequest`, `WebChatReply`, `WebChatConversationSummary`
- 모두 `dataclasses.dataclass(frozen=True)`
- `from __future__ import annotations` 사용 금지 (CLAUDE.md 규칙)

### Step 4. service 계층
`service.py`의 핵심 함수: `send_web_chat_message(user, conversation_id, text) -> WebChatReply`

흐름:
1. ownership 검증 (Step 7 머지 후 `list_conversations`로 보강. 1차에서는 TODO)
2. `message_id = f"web:{uuid.uuid4().hex}"`
3. `append_message(user.user_id, {"role": "user", "content": text}, conversation_id=conversation_id, metadata={"source": "web", "message_id": message_id})`
4. `incoming = CubeIncomingMessage(user_id=user.user_id, user_name=user.user_name, channel_id=conversation_id, message_id=message_id, message=text)` (1차에서는 임시 재사용)
5. `from api.workflows.lg_orchestrator import handle_message` → `reply = handle_message(incoming)`
6. `append_message(user.user_id, {"role": "assistant", "content": reply.reply}, conversation_id=conversation_id, metadata={"source": "web", "workflow_id": reply.workflow_id})`
7. `WebChatReply(conversation_id, message_id, reply.reply, reply.workflow_id)` 반환

### Step 5. router endpoints
- `GET  /api/v1/web-chat/me`
- `GET  /api/v1/web-chat/conversations`
- `GET  /api/v1/web-chat/conversations/<conversation_id>/messages`
- `POST /api/v1/web-chat/conversations/<conversation_id>/messages`

요청 body의 `user_id`는 무시합니다. 모든 endpoint는 매 요청마다 `get_current_web_chat_user()` 호출.

### Step 6. 오류 처리 표준화
- 401: `Unauthorized` (LASTUSER 없음)
- 403: `Forbidden` (다른 사용자의 conversation 접근)
- 400: `BadRequest` (빈 메시지, JSON 파싱 실패)
- 5xx: workflow 또는 conversation store 예외 → 로그 후 응답
- workflow 실패 시 assistant 메시지를 저장하지 않음 (이중 저장 방지)
- JSON error envelope: `{"error": "...", "detail": "..."}`

### Step 7. conversation 목록 기능
- `api/conversation_service.py`에 `list_conversations(user_id, limit=20) -> list[ConversationSummary]` 추가
- 백엔드별(Mongo / 파일 / 메모리) 동작 보장
- metadata의 `source` 값("cube" 또는 "web")을 노출하여 어디서 시작된 대화인지 구분

### Step 8. backend 테스트
- `tests/test_web_chat_identity.py` — LASTUSER 누락/존재 양쪽
- `tests/test_web_chat_router.py` — endpoint 4종, body의 `user_id` 무시 검증
- `tests/test_web_chat_service.py` — `handle_message` monkeypatch + 저장 호출 검증
- `tests/test_conversation_service_list.py` — backend별 list 동작 + 본인 데이터만 반환
- 전략 문서 §14의 테스트 항목 전부 커버

### Step 9. Nuxt 앱 부트스트랩
- `web/package.json`, `web/nuxt.config.ts`, `web/app.vue`, `web/pages/index.vue`
- `nuxt.config.ts`: `ssr: false`, `modules: ['@nuxt/ui']`, `app.baseURL: '/chat/'`, `runtimeConfig.public.webChatApiBase: '/api/v1/web-chat'`
- 모든 `.vue` 파일은 `<template>` → `<script setup>` 순서 (CLAUDE.md 규칙)

### Step 10. composables / API 레이어
- `web/composables/useChatApi.ts`: `fetchCurrentUser`, `listConversations`, `fetchMessages`, `sendMessage`
- 모든 호출에 `credentials: 'include'`
- 타입은 `web/types/chat.ts`에 분리

### Step 11. 컴포넌트 분할
- `ChatTimeline.vue` — user/assistant 메시지 목록
- `ChatComposer.vue` — 입력창, 전송 버튼, loading/disabled
- `ConversationList.vue` — 최근 conversation 목록과 선택
- `ConversationHeader.vue` — 현재 사용자, 현재 대화, 연결 상태
- Nuxt UI 기본 컴포넌트(`UCard`, `UButton`, `UInput`, `UAvatar` 등) 우선 사용

### Step 12. Flask SPA serving
- 신규: `api/web_frontend/__init__.py`, `api/web_frontend/router.py`
- `bp = Blueprint("web_frontend", __name__)`
- `/chat` → `api/static/chat/index.html`
- `/chat/<path:rest>` → 동일 `index.html` (SPA fallback). `_nuxt` 자산은 `send_from_directory(api/static/chat/_nuxt, rest)`
- `/api/...`를 가로채지 않도록 prefix 분리에 주의
- `api/static/chat/.gitkeep`만 commit (빌드 산출물은 .gitignore)

### Step 13. 빌드/배포 절차
- `web/`에서 `npm run build` → `.output/public/` 산출
- 산출물을 `api/static/chat/`로 복사 (선택: `scripts/build_web_chat.sh` 또는 `Makefile` 항목)
- 운영은 단일 origin 가정. 별도 Node 프로세스 없음.

### Step 14. 운영 검증 체크리스트 (사무실/운영)
- SSO 통과 후 `LASTUSER` cookie가 Flask까지 도달
- `LASTUSER` 값이 Cube의 `unique_name`과 일치
- `AFM_MONGO_URI` 설정 + uWSGI multi-worker 환경에서 checkpoint 영속성
- Cube 장애 시뮬레이션 시 web 경로만으로 대화 지속

## 5. 병렬 작업 그룹 (파일 충돌 없는 단위)

아래 4개 그룹은 서로의 파일을 건드리지 않으므로 동시 진행 가능합니다. 각 그룹은 독립 PR 단위로 운영을 권장합니다.

| 그룹 | 작성/수정 파일 | 기존 파일 수정 | 의존성 | 비고 |
|------|----------------|----------------|--------|------|
| **A. 웹 채팅 백엔드 모듈** | `api/web_chat/__init__.py`, `models.py`, `identity.py`, `service.py`, `router.py` + `tests/test_web_chat_identity.py`, `test_web_chat_router.py`, `test_web_chat_service.py` | 없음 (모두 신규) | 없음 (자동 등록) | Step 1~6, 8 일부. 1차 ownership 검증은 TODO로 두고 진행 가능 |
| **B. conversation 목록 API** | `api/conversation_service.py` (수정), `tests/test_conversation_service_list.py` (신규) | `api/conversation_service.py` 1개 | 없음 | Step 7. 유일한 기존 파일 수정 작업 |
| **C. Flask SPA serving** | `api/web_frontend/__init__.py`, `api/web_frontend/router.py`, `api/static/chat/.gitkeep` | 없음 (모두 신규) | 없음 (자동 등록) | Step 12. Nuxt 빌드 산출물은 배포 시 주입 |
| **D. Nuxt 프런트엔드** | `web/package.json`, `nuxt.config.ts`, `app.vue`, `pages/index.vue`, `components/chat/*.vue`, `composables/useChatApi.ts`, `types/chat.ts` | 없음 (별도 디렉터리) | 없음 | Step 9~11. API 스펙(§4 Step 5)만 합의되면 백엔드와 병렬 진행 |

**통합 시점 (그룹 간 만남)**

- A의 ownership 검증을 완성하려면 B 머지 후 `service.py`에 `list_conversations` 호출을 연결합니다 (소수 라인 수정).
- D의 `useChatApi.ts`는 A의 endpoint 계약(§4 Step 5)을 따르며, A가 미머지여도 mock 응답으로 개발 가능합니다.
- C는 D의 `web/.output/public/`을 `api/static/chat/`로 복사하는 시점에만 만납니다. 코딩 단계에서는 완전 독립.

**빌드 스크립트 (선택)** — `scripts/build_web_chat.sh` 또는 `Makefile` 항목 신규. 어느 그룹에도 속하지 않는 별도 작업으로 분리 가능.

**권장 머지 순서** (충돌 회피용 순서이며, 코딩 자체는 병렬)

1. B (가장 작고 다른 그룹의 정합성 기반)
2. A (B의 새 함수 사용)
3. C, D (서로 독립, 어떤 순서든 무방)

## 6. 각 단계 완료 후 품질 루프 (필수)

모든 Step을 마친 직후 아래 2단계 루프를 거칩니다. 코드를 머지 후보로 올리기 전에 반드시 수행합니다.

1. **`/codex:review` 실행** — 해당 단계에서 작성/수정한 파일을 대상으로 외부 코드 리뷰. 보안·정합성·테스트 누락·프로젝트 컨벤션 위반(예: `from __future__ import annotations` 금지, `pathlib` 사용, 한국어 메시지)을 중점 확인.
2. **`/simplify` 실행** — 리뷰 결과를 바탕으로 단순화 패스. 과한 try/except, 불필요한 추상화, 데드 코드, 사용되지 않는 타입 힌트, 중복 헬퍼 제거. 견고하고 읽기 쉬운 코드로 정리.

**루프 종료 조건** — `/codex:review`가 새 high-priority 이슈를 보고하지 않고, `/simplify`가 추가 변경을 만들지 않을 때까지 (최대 2회 반복). 그래도 잔존 이슈가 있으면 별도 follow-up으로 분리하고 본 PR은 머지.

**루프 적용 단위** — 그룹 단위가 아니라 **Step 단위**. 예: Step 4 작성 직후 즉시 review→simplify 후 Step 5로 진행. 한 그룹의 여러 Step을 모은 뒤 한 번만 돌리지 않습니다.

**테스트 회귀 확인** — 루프 후 항상 `pytest tests/ -v`와 `ruff check .` 재실행.

## 7. 홈 개발 환경 가정 (필수)

본 프로젝트의 dev 패턴(`CLAUDE.md` 참조)에 따라 코딩과 1차 검증은 모두 **홈 환경**에서 수행합니다. Cube/Mongo/Redis/LLM 일부 URL이 아직 `.env`에 없으므로, 코드와 테스트는 다음을 모두 만족해야 합니다.

### a. 환경 변수 누락 허용
- `AFM_MONGO_URI`, `REDIS_URL` 등이 비어 있어도 import/부팅이 깨지지 않아야 합니다. 이미 `api/config.py`와 `conversation_service`가 빈 값 → in-memory fallback을 지원하므로 같은 패턴을 따릅니다.
- 새 코드는 모듈 import 시점에 외부 연결을 시도하지 않습니다 (lazy connect). config 읽기와 클라이언트 인스턴스화는 분리합니다.
- "URL은 나중에 `.env`에 채워질 것"이라고 **가정**하고 키 이름과 사용처는 정상 케이스 기준으로 작성합니다. 누락 시는 fallback 또는 명확한 경고 로그로만 처리하고 코드 분기를 늘리지 않습니다.

### b. 외부 서비스 호출 격리
- LangGraph checkpoint: `MongoDBSaver`가 안되면 자동으로 `MemorySaver`로 떨어지는 기존 구조를 그대로 사용. web_chat 코드는 fallback에 무관하게 동일 인터페이스로 호출합니다.
- LLM: 홈에서 LLM endpoint를 못 부르더라도 service 계층 단위 테스트가 동작하도록 `handle_message`를 mock 합니다 (`tests/test_cube_service.py` 패턴 참고).
- Cube 송신: web_chat은 호출하지 않으므로 영향 없음.

### c. 홈 dev 실행 절차 (수동 검증)
`.env`에 `LASTUSER`/Mongo/Redis 미설정 상태에서도 다음이 모두 작동해야 합니다.

```bash
python index.py
# 다른 터미널에서
curl -b "LASTUSER=devuser" http://localhost:5000/api/v1/web-chat/me
curl -b "LASTUSER=devuser" -X POST \
  -H "Content-Type: application/json" \
  -d '{"message":"안녕"}' \
  http://localhost:5000/api/v1/web-chat/conversations/dev-channel-1/messages
```

Nuxt: `cd web && npm run dev` 후 `/chat` 접속, 메시지 송수신 동작. Flask는 dev origin에 대해 CORS + cookie 정책을 임시 허용하거나 dev cookie를 주입해 테스트.

### d. 사무실/운영에서 별도 검증 (홈 검증 불가)
- SSO 통과 후 실제 `LASTUSER` cookie가 Flask까지 전달되는지
- `LASTUSER` 값이 Cube의 `unique_name`과 일치하여 같은 thread를 이어가는지
- `AFM_MONGO_URI` 설정 + uWSGI multi-worker 환경에서 checkpoint 영속성
- Cube 실제 장애 상황에서 web 경로만으로 대화 지속

### e. 테스트 작성 규칙
- 모든 새 pytest는 외부 서비스 없이 통과해야 합니다. Mongo/Redis/LLM/Cube는 `tests/conftest.py`나 개별 테스트의 mock으로 처리.
- `tests/test_web_chat_service.py`는 `handle_message`를 monkeypatch하여 stub `WorkflowReply`를 반환.
- `tests/test_web_chat_router.py`는 `client.get/post` + cookie 주입(`client.set_cookie`)으로만 검증하고 실제 LLM/DB는 호출하지 않습니다.
- `pytest tests/ -v`는 `.env` 비어 있어도 100% 통과해야 합니다.

## 8. 변경되는 파일/디렉터리 요약

| 종류 | 경로 | 그룹 |
|------|------|------|
| 신규 | `api/web_chat/__init__.py` | A |
| 신규 | `api/web_chat/models.py` | A |
| 신규 | `api/web_chat/identity.py` | A |
| 신규 | `api/web_chat/service.py` | A |
| 신규 | `api/web_chat/router.py` | A |
| 수정 | `api/conversation_service.py` | B |
| 신규 | `api/web_frontend/__init__.py` | C |
| 신규 | `api/web_frontend/router.py` | C |
| 신규 | `api/static/chat/.gitkeep` | C |
| 신규 | `web/package.json` | D |
| 신규 | `web/nuxt.config.ts` | D |
| 신규 | `web/app.vue` | D |
| 신규 | `web/pages/index.vue` | D |
| 신규 | `web/components/chat/ChatTimeline.vue` | D |
| 신규 | `web/components/chat/ChatComposer.vue` | D |
| 신규 | `web/components/chat/ConversationList.vue` | D |
| 신규 | `web/components/chat/ConversationHeader.vue` | D |
| 신규 | `web/composables/useChatApi.ts` | D |
| 신규 | `web/types/chat.ts` | D |
| 신규 | `tests/test_web_chat_identity.py` | A |
| 신규 | `tests/test_web_chat_router.py` | A |
| 신규 | `tests/test_web_chat_service.py` | A |
| 신규 | `tests/test_conversation_service_list.py` | B |
| 신규 (선택) | `scripts/build_web_chat.sh` 또는 `Makefile` 항목 | - |

## 9. 명시적 비범위 (Out-of-scope)

- Nuxt SSR 모드
- 별도 자체 로그인 화면
- WebSocket / SSE 스트리밍
- conversation 검색 / 페이지네이션 / 즐겨찾기
- 파일 업로드 (Cube 채널 업로드와의 통합 포함)
- multilingual i18n 자동화

이들은 1차 fallback 채널의 목적을 넘어서므로 별도 작업으로 분리합니다.

## 10. 검증 (Verification)

### 자동
- `ruff check .` / `ruff format --check .`
- `pytest tests/ -v` (특히 `test_web_chat_*`, `test_conversation_service_list`)

### 홈 수동
- `python index.py` → §7.c의 `curl` 시나리오 통과
- 같은 `user_id` + `conversation_id`로 두 번 POST → 두 번째 응답이 첫 번째 thread 상태를 인식하는지 (`build_thread_id` 로그 또는 LangGraph state 직접 확인)
- Nuxt: `cd web && npm run dev` → `/chat`에서 메시지 송수신 동작

### 사무실/운영 수동
- §4 Step 14의 체크리스트 4항목

## 11. 작성 후속작업

본 코딩 계획서 추가는 doc 단일 커밋으로 분리합니다. 이후 실제 구현은 §5의 그룹 단위로 분리 PR로 진행하며, 각 Step 완료마다 §6의 품질 루프를 거칩니다.
