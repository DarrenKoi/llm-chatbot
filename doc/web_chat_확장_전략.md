# Cube 장애 대비 웹 채팅 확장 전략

## 1. 목적

이 문서는 Cube가 일시적으로 사용할 수 없을 때 사용자가 Flask에서 제공하는 웹 페이지에 접속해 기존 대화를 이어갈 수 있도록 웹 채팅 기능을 확장하는 계획을 정리합니다.

목표는 새로운 챗봇을 별도로 만드는 것이 아니라, 현재 Cube 경로에서 사용 중인 대화 저장소와 LangGraph checkpoint를 웹 채널에서도 같은 방식으로 재사용하는 것입니다.

## 2. 가능 여부

가능합니다. 현재 저장소는 이미 아래 구조를 갖고 있습니다.

- `api/conversation_service.py`는 `user_id`와 `conversation_id` 기준으로 대화 이력을 저장합니다.
- `api/workflows/langgraph_checkpoint.py`의 `build_thread_id(user_id, channel_id)`는 LangGraph `thread_id`를 `user_id::channel_id` 형식으로 만듭니다.
- `api/workflows/lg_orchestrator.py`의 `handle_message()`는 동일한 `thread_id`로 `graph.get_state()`를 읽고, 대기 중인 task가 있으면 `Command(resume=...)`로 이어서 처리합니다.
- `api/cube/service.py`는 Cube 메시지를 저장하고 workflow를 호출한 뒤 Cube로 다시 전송하는 전체 파이프라인을 갖고 있습니다.

따라서 웹 채팅도 같은 `user_id`와 같은 `channel_id`를 사용하면 같은 LangGraph checkpoint를 계속 사용할 수 있습니다.

단, 운영 환경에서 checkpoint를 유지하려면 `AFM_MONGO_URI`가 설정되어 `MongoDBSaver`를 사용해야 합니다. `MemorySaver` fallback 상태에서는 프로세스 재시작, worker 분산, uWSGI worker 차이에 따라 대화 이어가기 품질이 깨질 수 있습니다.

## 3. 핵심 설계 원칙

웹 채팅은 Cube의 대체 입구입니다. 따라서 Cube 전송 로직은 재사용하지 않고, 아래 공통 처리만 공유해야 합니다.

1. 사용자 메시지를 conversation store에 저장합니다.
2. 같은 `user_id`와 `channel_id`로 LangGraph workflow를 호출합니다.
3. assistant 응답을 conversation store에 저장합니다.
4. 응답을 Cube가 아니라 웹 API JSON으로 반환합니다.

즉, `api.cube.service.process_incoming_message()`를 그대로 호출하면 안 됩니다. 해당 함수는 마지막에 `send_multimessage()` 또는 rich notification 전송을 수행하므로 웹 채팅 API에는 맞지 않습니다.

초기 구현에서는 `CubeIncomingMessage` 데이터 구조를 임시로 재사용할 수 있습니다. 다만 장기적으로는 workflow 계층이 Cube 이름에 의존하지 않도록 `IncomingMessage` 같은 중립 모델로 분리하는 것이 좋습니다.

## 4. 권장 파일 구조

Nuxt는 Flask와 별도로 개발하되, 운영에서는 정적 파일로 빌드해 Flask가 제공하는 방식을 우선 권장합니다. 이렇게 하면 운영 서버에서 Node 프로세스를 따로 띄우지 않아도 됩니다.

```text
llm-chatbot/
  api/
    web_chat/
      __init__.py
      router.py
      service.py
      models.py
      identity.py
    web_frontend/
      __init__.py
      router.py
    static/
      chat/
        index.html
        _nuxt/
          ...

  web/
    package.json
    nuxt.config.ts
    app.vue
    pages/
      chat.vue
    components/
      chat/
        ChatTimeline.vue
        ChatComposer.vue
        ConversationList.vue
        ConversationHeader.vue
    composables/
      useChatApi.ts
    types/
      chat.ts

  tests/
    test_web_chat_router.py
    test_web_chat_service.py
```

### 4.1 `api/web_chat/`

웹 채팅의 Flask JSON API를 담당합니다.

- `router.py`: `/api/v1/web-chat/...` endpoint를 정의합니다.
- `service.py`: 메시지 저장, workflow 호출, assistant 응답 저장을 담당합니다.
- `models.py`: 요청과 응답 DTO를 정의합니다.
- `identity.py`: 현재 사용자의 `user_id`, `user_name`을 서버 측에서 결정합니다.

현재 `api/blueprint_loader.py`가 `router.py`를 자동 탐색하므로 `api/web_chat/router.py`에 Blueprint를 만들면 별도 등록 없이 Flask app에 붙일 수 있습니다.

### 4.2 `api/web_frontend/`

Nuxt 빌드 결과물을 Flask에서 제공하는 라우터입니다.

- `/chat`은 Nuxt `index.html`을 반환합니다.
- `/chat/<path>`도 같은 `index.html`을 반환해 SPA 라우팅을 허용합니다.
- `_nuxt` asset은 `api/static/chat/_nuxt/...` 아래 정적 파일로 제공합니다.

초기에는 별도 Blueprint 없이 `create_application()`에 route를 직접 추가할 수도 있지만, 확장성을 생각하면 `api/web_frontend/router.py`로 분리하는 편이 좋습니다.

### 4.3 `web/`

Nuxt 소스 디렉터리입니다. 이 디렉터리는 Python app과 분리해 관리합니다.

개발 중에는 Nuxt dev server를 띄워 Flask API를 호출합니다. 운영 배포 전에는 Nuxt를 static build하고 결과물을 `api/static/chat/` 또는 배포 artifact 경로로 복사합니다.

## 5. API 설계

권장 endpoint는 아래와 같습니다.

```text
GET  /api/v1/web-chat/conversations
GET  /api/v1/web-chat/conversations/<conversation_id>/messages
POST /api/v1/web-chat/conversations/<conversation_id>/messages
```

`POST /messages` 요청 예시는 아래와 같습니다.

```json
{
  "message": "번역 workflow 이어서 진행해 주세요."
}
```

응답 예시는 아래와 같습니다.

```json
{
  "conversation_id": "cube-channel-123",
  "message_id": "web:8d0f4c7e9b4f4c3e",
  "reply": "목표 언어를 알려주세요.",
  "workflow_id": "translator"
}
```

브라우저가 `user_id`를 직접 보내게 만들지 않는 것이 중요합니다. `user_id`는 사내 SSO, 세션, reverse proxy header 같은 신뢰 가능한 서버 측 정보에서 결정해야 합니다.

## 6. Checkpoint 유지 전략

웹에서 Cube 대화를 이어가려면 두 값이 같아야 합니다.

```text
user_id = Cube에서 사용하던 사용자 ID
channel_id = Cube에서 사용하던 채널 ID
```

현재 LangGraph thread는 아래처럼 만들어집니다.

```text
thread_id = user_id::channel_id
```

따라서 웹 fallback URL은 내부적으로 같은 `channel_id`를 선택할 수 있어야 합니다.

운영 정책은 두 가지 중 하나를 선택해야 합니다.

1. 사용자가 최근 Cube 대화방 목록에서 이어갈 대화를 선택합니다.
2. 웹 전용 대화는 `web:<uuid>` 형식의 새 `conversation_id`를 만들고, Cube 대화와는 별도 thread로 취급합니다.

Cube 장애 시에도 기존 Cube 대화를 이어가는 것이 목표라면 1번이 더 맞습니다. 이 경우 `conversation_service`에서 사용자별 최근 `conversation_id` 목록을 조회하는 기능을 추가해야 합니다.

## 7. 서비스 계층 처리 흐름

`api/web_chat/service.py`의 핵심 흐름은 아래와 같습니다.

```text
send_web_chat_message(user, conversation_id, text)
  -> message_id 생성
  -> append_message(user_id, user message, conversation_id)
  -> handle_workflow_message(incoming)
  -> append_message(user_id, assistant reply, conversation_id)
  -> WebChatReply 반환
```

초기 구현에서는 아래처럼 현재 구조를 최소 변경으로 사용할 수 있습니다.

```python
incoming = CubeIncomingMessage(
    user_id=user.user_id,
    user_name=user.user_name,
    channel_id=conversation_id,
    message_id=f"web:{uuid.uuid4().hex}",
    message=text,
)
workflow_result = handle_workflow_message(incoming)
```

장기 개선에서는 `api/cube/models.py`의 `CubeIncomingMessage`를 공통 모델로 끌어올리는 것이 좋습니다.

```text
api/messages/models.py
  IncomingMessage
  HandledMessage
```

그 후 Cube와 web chat이 모두 같은 공통 모델을 사용하도록 정리합니다.

## 8. Nuxt 화면 구성

첫 화면은 별도 홍보 페이지가 아니라 실제 채팅 화면이어야 합니다.

권장 UI 구성은 아래와 같습니다.

- 좌측 또는 상단: 대화 목록
- 중앙: 메시지 timeline
- 하단: 입력 composer
- 상단 header: 현재 대화 ID, 연결 상태, 새 대화 버튼
- 오류 상태: LLM/API 오류, checkpoint store 오류, 인증 오류를 구분해 표시

Nuxt 컴포넌트 역할은 아래처럼 나눕니다.

- `ChatTimeline.vue`: user/assistant 메시지 목록 표시
- `ChatComposer.vue`: 입력창, 전송 버튼, loading/disabled 상태
- `ConversationList.vue`: 최근 conversation 목록과 선택
- `ConversationHeader.vue`: 현재 대화 정보와 상태 표시
- `useChatApi.ts`: Flask API 호출을 캡슐화

## 9. 인증과 보안

가장 중요한 보안 요구사항은 브라우저 입력을 신뢰하지 않는 것입니다.

- 브라우저가 보낸 `user_id`를 그대로 사용하지 않습니다.
- 서버에서 현재 사용자를 식별합니다.
- 사용자가 요청한 `conversation_id`가 해당 사용자의 것인지 확인합니다.
- 운영 환경에서는 CSRF 또는 same-site cookie 정책을 검토합니다.
- 사내 reverse proxy가 사용자 정보를 header로 넘긴다면 허용된 proxy에서 온 header만 신뢰합니다.

이 검증이 없으면 다른 사용자의 `user_id`와 `conversation_id`를 추측해 checkpoint나 대화 이력에 접근할 수 있습니다.

## 10. 배포 전략

### 10.1 1차 권장안: Nuxt static build + Flask serving

가장 단순한 운영 구조입니다.

```text
Browser
  -> Flask /chat
  -> Nuxt static assets
  -> Flask /api/v1/web-chat
  -> conversation store + LangGraph checkpoint
```

장점은 다음과 같습니다.

- Flask/uWSGI 운영 구조를 크게 바꾸지 않습니다.
- Node SSR 서버가 필요 없습니다.
- API와 화면이 같은 origin이므로 CORS 설정이 단순합니다.

### 10.2 대안: Nuxt SSR 별도 운영

Nuxt SSR이 꼭 필요하면 Flask와 Nuxt를 별도 서비스로 운영할 수 있습니다. 다만 이 경우 reverse proxy, CORS, session 공유, 배포 단위가 늘어납니다.

현재 목적은 Cube 장애 대비 fallback 채널이므로 1차 구현에서는 static SPA가 더 적합합니다.

## 11. 단계별 도입 계획

### 1단계. 웹 채팅 backend API 추가

- `api/web_chat/router.py` 추가
- `api/web_chat/service.py` 추가
- 같은 `conversation_id`로 `handle_workflow_message()` 호출
- 사용자 메시지와 assistant 메시지를 `conversation_service`에 저장
- pytest로 저장, workflow 호출, 오류 응답을 검증

### 2단계. conversation 목록 API 추가

- 사용자별 최근 `conversation_id` 목록 조회 기능 추가
- Cube channel과 web conversation을 함께 보여줄 수 있도록 source metadata 정리
- conversation store backend별로 같은 동작을 보장

### 3단계. Nuxt chat UI 추가

- `web/` 디렉터리에 Nuxt app 생성
- `/chat` 첫 화면을 실제 채팅 UI로 구성
- 메시지 전송, 응답 표시, loading, error 상태 구현
- Flask API와 같은 origin 기준으로 연동

### 4단계. Flask static serving 추가

- Nuxt build 결과물을 `api/static/chat/` 또는 별도 artifact 위치에 배치
- `/chat`과 `/chat/<path>` route 추가
- asset cache header와 404 fallback 정책 정리

### 5단계. 운영 검증

- Mongo checkpoint persistence가 켜진 상태에서 Cube와 web이 같은 thread를 이어가는지 확인
- uWSGI worker가 여러 개일 때도 checkpoint가 유지되는지 확인
- Cube 장애 상황에서 web 경로만으로 대화가 이어지는지 확인
- 인증 header/session이 올바르게 매핑되는지 확인

## 12. 테스트 계획

최소 테스트는 아래를 포함해야 합니다.

- `POST /api/v1/web-chat/conversations/<id>/messages`가 사용자 메시지를 저장하는지 검증합니다.
- workflow 응답을 assistant 메시지로 저장하는지 검증합니다.
- 같은 `user_id`와 `conversation_id`로 호출할 때 `thread_id`가 유지되는지 검증합니다.
- 다른 사용자가 같은 `conversation_id`에 접근할 수 없는지 검증합니다.
- conversation store 오류가 발생하면 5xx 응답과 로그가 남는지 검증합니다.
- workflow 오류가 발생하면 assistant 메시지를 잘못 저장하지 않는지 검증합니다.

## 13. 주의할 점

- Cube fallback이라고 해서 Cube service 함수를 그대로 재사용하면 Cube 전송 side effect가 발생합니다.
- `conversation_id`와 `channel_id` 용어가 섞여 있으므로 API 문서에서는 하나를 주 용어로 정해야 합니다. 내부 구현에서는 기존 코드와 맞추기 위해 `channel_id`를 계속 사용할 수 있습니다.
- checkpoint 유지의 핵심은 message history가 아니라 LangGraph `thread_id`입니다. message history만 같아도 `thread_id`가 다르면 interrupt/resume 상태는 이어지지 않습니다.
- 운영에서 `MemorySaver`를 사용하면 fallback 목적을 충분히 달성하기 어렵습니다.
- 웹에서 새 대화를 만드는 경우 Cube 대화와 같은 thread로 이어지지 않는 것이 정상입니다.

## 14. 최종 권장안

이 저장소에는 아래 방식이 가장 적합합니다.

1. Flask는 기존처럼 주 서버로 유지합니다.
2. Nuxt는 `web/` 아래에서 개발하고 static build 결과만 Flask가 제공합니다.
3. 웹 채팅 API는 `api/web_chat/`에 별도 모듈로 둡니다.
4. workflow 호출은 `api.workflows.lg_orchestrator.handle_message()`를 공유합니다.
5. Cube 전송 함수는 웹 채팅 경로에서 호출하지 않습니다.
6. 같은 대화를 이어가야 할 때는 반드시 같은 `user_id`와 같은 `conversation_id/channel_id`를 사용합니다.
7. 장기적으로 `CubeIncomingMessage`를 공통 `IncomingMessage` 모델로 분리합니다.

이 순서로 확장하면 Cube 장애 대비 웹 채널을 추가하면서도 현재 LangGraph checkpoint, conversation store, workflow registry 구조를 크게 흔들지 않고 재사용할 수 있습니다.
