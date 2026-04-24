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

## 9. 라이브러리 검토

웹 채팅 기능은 라이브러리 하나로 전부 해결하기보다는 역할을 나누어 판단하는 것이 좋습니다.

이 저장소에서 직접 해결해야 하는 핵심은 아래입니다.

- 사내 사용자 식별
- `conversation_id/channel_id` 권한 검증
- `conversation_service` 저장
- LangGraph `thread_id` 유지
- Cube 전송 side effect 없이 workflow 호출

반대로 라이브러리로 도움을 받을 수 있는 부분은 아래입니다.

- 채팅 메시지 목록 UI
- 입력 composer UI
- 자동 scroll, loading, stop/retry 상태
- streaming 응답 표시
- tool/reasoning/event 표시 형식

### 9.1 Nuxt UI AI Chat

Nuxt UI v4에는 AI Chat 계열 컴포넌트가 있습니다.

- `UChatMessages`
- `UChatMessage`
- `UChatPrompt`
- `UChatPromptSubmit`
- `UChatReasoning`
- `UChatTool`
- `UChatPalette`

Nuxt UI 문서는 이 컴포넌트들이 Vercel AI SDK와 함께 streaming, reasoning, tool calling UI를 만들도록 설계되어 있다고 설명합니다. `UChatMessages`는 메시지 목록, 자동 scroll, loading indicator 같은 UI 동작을 이미 제공합니다.

권장 방식은 Nuxt UI를 채팅 화면의 기본 UI 부품으로 사용하는 것입니다. 이렇게 하면 우리가 직접 만들어야 하는 UI boilerplate를 줄일 수 있습니다.

다만 Nuxt UI는 backend checkpoint, 권한 검증, conversation store를 해결해 주지는 않습니다. 이 부분은 계속 Flask에서 직접 구현해야 합니다.

참고:

- <https://ui.nuxt.com/docs/components/chat>
- <https://ui.nuxt.com/docs/components/chat-messages>
- <https://ui.nuxt.com/docs/components/chat-message>
- <https://ui.nuxt.com/docs/components/chat-prompt>

### 9.2 Vercel AI SDK / `@ai-sdk/vue`

Vercel AI SDK는 Nuxt/Vue용 `@ai-sdk/vue`를 제공합니다. `Chat` class 또는 `useChat()` 계열 API를 사용하면 messages, status, send, stop, regenerate, stream 상태를 프론트엔드에서 일관되게 관리할 수 있습니다.

장점은 아래입니다.

- chat state 관리가 이미 준비되어 있습니다.
- `UIMessage`와 `parts` 형식이 Nuxt UI Chat 컴포넌트와 잘 맞습니다.
- streaming, tool call, resume stream 같은 기능을 점진적으로 붙이기 쉽습니다.

주의할 점은 서버 예제가 주로 Nuxt server route 또는 Node/TypeScript backend를 기준으로 한다는 점입니다. 현재 저장소는 Flask/Python 안에서 LangGraph를 직접 실행합니다. 따라서 AI SDK를 완전히 활용하려면 Flask가 AI SDK의 UI message stream protocol에 맞는 응답을 내보내거나, Nuxt server route를 중간 adapter로 두어야 합니다.

권장 판단은 아래입니다.

- 1차 구현: 직접 만든 `useChatApi.ts`로 Flask JSON API를 호출합니다.
- 2차 구현: streaming UX가 필요해지면 `@ai-sdk/vue`의 `Chat` class와 `UIMessage` 형식을 도입합니다.
- 3차 구현: Flask streaming 응답을 AI SDK stream protocol에 맞추거나, Nuxt server route adapter를 검토합니다.

참고:

- <https://ai-sdk.dev/docs/getting-started/nuxt>
- <https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat>
- <https://ai-sdk.dev/docs/ai-sdk-ui/transport>
- <https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-resume-streams>

### 9.3 LangGraph Platform / LangGraph SDK

LangGraph Platform은 threads, runs, streaming API를 제공하며, stream 재연결과 thread 기반 실행 모델을 지원합니다. 이 방향은 LangGraph 실행 자체를 Flask 내부 함수 호출에서 외부 agent server 호출로 바꾸는 선택에 가깝습니다.

장점은 아래입니다.

- LangGraph의 thread/run 개념과 웹 채팅이 자연스럽게 맞습니다.
- streaming, resumability, human-in-the-loop 같은 기능을 표준 API로 받을 수 있습니다.
- frontend가 Python Flask 내부 구현을 덜 알게 됩니다.

단점은 아래입니다.

- 현재 `api/workflows/lg_orchestrator.py` 중심 구조를 배포형 LangGraph agent 구조로 옮겨야 합니다.
- 운영 단위와 인증, 배포, 관측 체계가 커집니다.
- Cube fallback용 1차 웹 채팅에는 과한 변경입니다.

권장 판단은 단기 도입 대상이 아닙니다. 여러 프론트엔드 채널, 장시간 실행 workflow, 외부 agent server 운영이 필요해질 때 중장기 후보로 검토합니다.

참고:

- <https://docs.langchain.com/langsmith/streaming>
- <https://reference.langchain.com/javascript/functions/_langchain_langgraph-sdk.react.useStream.html>

### 9.4 AG-UI

AG-UI는 agent backend와 사용자 UI 사이의 event 기반 protocol입니다. 문서상 LangGraph integration을 지원하며, streaming chat, shared state, frontend tool calls, interrupts 같은 agent UI 이벤트를 표준화하려는 목적을 갖고 있습니다.

장점은 아래입니다.

- chat을 단순 text request/response가 아니라 event stream으로 설계할 수 있습니다.
- tool event, interrupt, shared state 같은 확장 요구가 생길 때 구조가 좋아집니다.
- backend와 frontend 사이의 임의 JSON 규격이 커지는 문제를 줄일 수 있습니다.

단점은 아래입니다.

- 현재 Vue/Nuxt 전용 client component 선택지는 Nuxt UI나 AI SDK보다 직접적이지 않습니다.
- 이 저장소의 1차 목표인 Cube fallback 채널에는 protocol 도입 비용이 큽니다.
- AG-UI를 쓰더라도 인증, conversation 권한, LangGraph checkpoint mapping은 직접 해결해야 합니다.

권장 판단은 지금 바로 전체 도입하지 않는 것입니다. 다만 향후 streaming event 규격을 정할 때 참고할 후보로 남겨둘 가치가 있습니다.

참고:

- <https://docs.ag-ui.com/introduction>
- <https://docs.ag-ui.com/concepts/agents>

### 9.5 Chainlit

Chainlit은 Python 기반 conversational AI app을 빠르게 만들 수 있는 도구이며 LangChain/LangGraph integration 예제를 제공합니다.

장점은 아래입니다.

- Python 코드만으로 빠르게 chat UI를 만들 수 있습니다.
- LangGraph와의 연결 예제가 있습니다.
- 내부 prototype이나 workflow debugging UI로는 유용합니다.

단점은 아래입니다.

- 별도 Chainlit app/runtime을 운영하는 형태가 됩니다.
- Nuxt를 익숙한 frontend로 쓰려는 방향과 다릅니다.
- Flask가 `/chat`을 제공하는 현재 확장 계획과는 운영 모델이 맞지 않습니다.

권장 판단은 production fallback 경로가 아니라 내부 prototype 또는 workflow 개발 도구 후보입니다.

참고:

- <https://docs.chainlit.io/get-started/overview>
- <https://docs.chainlit.io/integrations/langchain>

### 9.6 Gradio / Streamlit

Gradio와 Streamlit도 chat UI를 빠르게 만들 수 있습니다. Streamlit은 `st.chat_message`, `st.chat_input` 같은 chat element를 제공하고, Gradio는 `gr.Chatbot` 컴포넌트를 제공합니다.

장점은 아래입니다.

- 빠른 demo에 적합합니다.
- Python 중심으로 구현할 수 있습니다.
- 별도 frontend 개발 부담이 작습니다.

단점은 아래입니다.

- Flask/Nuxt에 자연스럽게 내장되는 구조가 아닙니다.
- 사내 웹 UI와 동일한 디자인, route, 인증 정책을 맞추기 어렵습니다.
- Cube fallback용 운영 페이지로 쓰기에는 통합 비용이 다시 발생합니다.

권장 판단은 운영 fallback이 아니라 demo 또는 실험용입니다.

참고:

- <https://docs.streamlit.io/library/api-reference/chat>
- <https://www.gradio.app/main/docs/gradio/chatbot>

### 9.7 직접 구현 난이도

이 저장소 기준으로 1차 웹 채팅 backend는 직접 구현하기 쉽습니다. 이유는 이미 필요한 핵심 기반이 있기 때문입니다.

- 대화 이력 저장: `api/conversation_service.py`
- checkpoint thread 생성: `api/workflows/langgraph_checkpoint.py`
- workflow 호출: `api/workflows/lg_orchestrator.py`
- Flask route 자동 등록: `api/blueprint_loader.py`

처음부터 어렵게 만들 필요는 없습니다. 1차는 non-streaming JSON API로 충분합니다.

```text
POST /api/v1/web-chat/conversations/<conversation_id>/messages
  -> user message 저장
  -> handle_workflow_message()
  -> assistant reply 저장
  -> JSON 반환
```

실제로 어려운 부분은 chat API 자체가 아니라 아래입니다.

- 현재 사용자를 신뢰 가능하게 식별하는 방식
- 사용자가 접근 가능한 `conversation_id`인지 검증하는 방식
- Cube channel과 web conversation의 매핑 정책
- Mongo checkpoint persistence 운영 보장
- 장시간 응답과 streaming 재연결 UX

따라서 권장 결론은 아래입니다.

1. Backend chat service는 직접 구현합니다.
2. Frontend UI는 Nuxt UI AI Chat 컴포넌트를 적극적으로 사용합니다.
3. Frontend state는 1차에서는 직접 composable로 관리하고, streaming이 필요해질 때 `@ai-sdk/vue` 도입을 검토합니다.
4. AG-UI와 LangGraph Platform은 장기적으로 event protocol과 agent server 운영이 필요할 때 재평가합니다.

## 10. 인증과 보안

가장 중요한 보안 요구사항은 브라우저 입력을 신뢰하지 않는 것입니다.

- 브라우저가 보낸 `user_id`를 그대로 사용하지 않습니다.
- 서버에서 현재 사용자를 식별합니다.
- 사용자가 요청한 `conversation_id`가 해당 사용자의 것인지 확인합니다.
- 운영 환경에서는 CSRF 또는 same-site cookie 정책을 검토합니다.
- 사내 reverse proxy가 사용자 정보를 header로 넘긴다면 허용된 proxy에서 온 header만 신뢰합니다.

이 검증이 없으면 다른 사용자의 `user_id`와 `conversation_id`를 추측해 checkpoint나 대화 이력에 접근할 수 있습니다.

## 11. 배포 전략

### 11.1 1차 권장안: Nuxt static build + Flask serving

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

### 11.2 대안: Nuxt SSR 별도 운영

Nuxt SSR이 꼭 필요하면 Flask와 Nuxt를 별도 서비스로 운영할 수 있습니다. 다만 이 경우 reverse proxy, CORS, session 공유, 배포 단위가 늘어납니다.

현재 목적은 Cube 장애 대비 fallback 채널이므로 1차 구현에서는 static SPA가 더 적합합니다.

## 12. 단계별 도입 계획

### 12.1 웹 채팅 backend API 추가

- `api/web_chat/router.py` 추가
- `api/web_chat/service.py` 추가
- 같은 `conversation_id`로 `handle_workflow_message()` 호출
- 사용자 메시지와 assistant 메시지를 `conversation_service`에 저장
- pytest로 저장, workflow 호출, 오류 응답을 검증

### 12.2 conversation 목록 API 추가

- 사용자별 최근 `conversation_id` 목록 조회 기능 추가
- Cube channel과 web conversation을 함께 보여줄 수 있도록 source metadata 정리
- conversation store backend별로 같은 동작을 보장

### 12.3 Nuxt chat UI 추가

- `web/` 디렉터리에 Nuxt app 생성
- `/chat` 첫 화면을 실제 채팅 UI로 구성
- 메시지 전송, 응답 표시, loading, error 상태 구현
- Flask API와 같은 origin 기준으로 연동

### 12.4 Flask static serving 추가

- Nuxt build 결과물을 `api/static/chat/` 또는 별도 artifact 위치에 배치
- `/chat`과 `/chat/<path>` route 추가
- asset cache header와 404 fallback 정책 정리

### 12.5 운영 검증

- Mongo checkpoint persistence가 켜진 상태에서 Cube와 web이 같은 thread를 이어가는지 확인
- uWSGI worker가 여러 개일 때도 checkpoint가 유지되는지 확인
- Cube 장애 상황에서 web 경로만으로 대화가 이어지는지 확인
- 인증 header/session이 올바르게 매핑되는지 확인

## 13. 테스트 계획

최소 테스트는 아래를 포함해야 합니다.

- `POST /api/v1/web-chat/conversations/<id>/messages`가 사용자 메시지를 저장하는지 검증합니다.
- workflow 응답을 assistant 메시지로 저장하는지 검증합니다.
- 같은 `user_id`와 `conversation_id`로 호출할 때 `thread_id`가 유지되는지 검증합니다.
- 다른 사용자가 같은 `conversation_id`에 접근할 수 없는지 검증합니다.
- conversation store 오류가 발생하면 5xx 응답과 로그가 남는지 검증합니다.
- workflow 오류가 발생하면 assistant 메시지를 잘못 저장하지 않는지 검증합니다.

## 14. 주의할 점

- Cube fallback이라고 해서 Cube service 함수를 그대로 재사용하면 Cube 전송 side effect가 발생합니다.
- `conversation_id`와 `channel_id` 용어가 섞여 있으므로 API 문서에서는 하나를 주 용어로 정해야 합니다. 내부 구현에서는 기존 코드와 맞추기 위해 `channel_id`를 계속 사용할 수 있습니다.
- checkpoint 유지의 핵심은 message history가 아니라 LangGraph `thread_id`입니다. message history만 같아도 `thread_id`가 다르면 interrupt/resume 상태는 이어지지 않습니다.
- 운영에서 `MemorySaver`를 사용하면 fallback 목적을 충분히 달성하기 어렵습니다.
- 웹에서 새 대화를 만드는 경우 Cube 대화와 같은 thread로 이어지지 않는 것이 정상입니다.

## 15. 최종 권장안

이 저장소에는 아래 방식이 가장 적합합니다.

1. Flask는 기존처럼 주 서버로 유지합니다.
2. Nuxt는 `web/` 아래에서 개발하고 static build 결과만 Flask가 제공합니다.
3. 웹 채팅 API는 `api/web_chat/`에 별도 모듈로 둡니다.
4. workflow 호출은 `api.workflows.lg_orchestrator.handle_message()`를 공유합니다.
5. Cube 전송 함수는 웹 채팅 경로에서 호출하지 않습니다.
6. 같은 대화를 이어가야 할 때는 반드시 같은 `user_id`와 같은 `conversation_id/channel_id`를 사용합니다.
7. 장기적으로 `CubeIncomingMessage`를 공통 `IncomingMessage` 모델로 분리합니다.

이 순서로 확장하면 Cube 장애 대비 웹 채널을 추가하면서도 현재 LangGraph checkpoint, conversation store, workflow registry 구조를 크게 흔들지 않고 재사용할 수 있습니다.
