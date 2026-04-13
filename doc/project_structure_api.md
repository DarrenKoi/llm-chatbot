# API Package Structure

이 문서는 현재 코드 기준으로 `api/` 패키지의 구조와 실제 메시지 흐름을 정리한다.
핵심 추적 대상은 `Cube 수신 -> 큐 적재 -> worker 처리 -> LangGraph workflow -> LLM/MCP -> Cube 응답` 경로다.

## 상위 구조

```text
api/
├── __init__.py
├── blueprint_loader.py
├── config.py
├── conversation_service.py
├── monitoring_service.py
├── archive/
├── cube/
├── file_delivery/
├── html_templates/
├── llm/
├── mcp/
├── profile/
├── scheduled_tasks/
├── utils/
└── workflows/
```

## 공용 파일

- `api/__init__.py`: Flask 앱 생성, 기본 페이지 등록, Blueprint 자동 등록, 공통 요청 로깅을 담당한다.
- `api/blueprint_loader.py`: `router.py` 계열 파일을 찾아 Blueprint를 자동 로드한다.
- `api/config.py`: Cube, Redis, MongoDB, LLM, 파일 저장 경로, LangGraph 체크포인터 등 환경 기반 설정을 모은다.
- `api/conversation_service.py`: 사용자/채널 기준 대화 이력을 관리한다. MongoDB, 로컬 파일, 메모리 백엔드를 지원한다.
- `api/monitoring_service.py`: 운영 페이지에서 보여줄 상태 요약을 만든다.

## 하위 패키지

### `api/cube/`

Cube 메시지 입구와 비동기 처리 경계를 담당한다.

- `router.py`: `/api/v1/cube/receiver` 엔드포인트를 제공한다.
- `payload.py`: Cube payload에서 `user_id`, `channel_id`, `message_id`, `message` 등을 추출한다.
- `service.py`: 수신 메시지 검증, 큐 적재, 대화 이력 저장, workflow 호출, Cube 응답 전송을 담당한다.
- `queue.py`: Redis 기반 큐 적재/중복 방지 처리를 맡는다.
- `worker.py`: 큐에서 메시지를 꺼내 실제 처리 함수를 호출한다.
- `client.py`: Cube `multiMessage` 전송 클라이언트다.
- `models.py`: Cube 관련 입력/출력 모델을 정의한다.

### `api/file_delivery/`

파일 업로드와 다운로드 기능을 담당한다.

- `router.py`: 업로드 API, 파일 제공 API, 파일 전달 페이지를 제공한다.
- `file_delivery_service.py`: 원본 저장, 메타데이터 저장, 이미지 variant 생성, 만료 파일 정리를 담당한다.
- `__init__.py`: 외부에서 쓰는 파일 전달 기능을 재노출한다.

### `api/archive/`

아카이브/OpenSearch 연동 코드다.

- `extractor.py`: 워크플로 상태/응답을 아카이브 문서로 변환한다.
- `service.py`: 아카이브 저장 흐름을 제공한다.
- `opensearch_client.py`: OpenSearch 연동 클라이언트다.
- `models.py`: 아카이브 관련 모델을 정의한다.

### `api/llm/`

LLM 호출과 시스템 프롬프트 구성을 담당한다.

- `service.py`: `ChatOpenAI` 호출, 메시지 조립, 응답 문자열 추출을 담당한다.
- `prompt/system.py`: 기본 시스템 프롬프트, 한국 시간대 문맥, 사용자 프로필 문맥을 합성한다.

### `api/mcp/`

MCP 도구 실행 경계를 담당한다.

- `models.py`: `MCPServerConfig`, `MCPTool`, `MCPToolCall`, `MCPToolResult`를 정의한다.
- `registry.py`: 서버/도구 메타데이터를 메모리 레지스트리에 등록/조회한다.
- `local_tools.py`: 로컬 Python 핸들러 등록/조회 기능을 제공한다.
- `executor.py`: 로컬 핸들러 우선 실행 후 필요 시 `MCPClient`로 폴백한다.
- `client.py`: 원격 MCP 호출용 얇은 클라이언트 스텁이다.
- `tool_selector.py`: workflow의 `tool_tags` 기준으로 도구 후보를 고른다.
- `errors.py`: MCP 관련 예외를 정의한다.

### `api/profile/`

사용자 프로필을 workflow/프롬프트에 주입하기 위한 계층이다.

- `service.py`: 사용자 프로필 로드와 fallback 처리를 담당한다.
- `models.py`: 프로필 모델을 정의한다.

### `api/scheduled_tasks/`

정기 작업과 실행 상태 점검 영역이다.

- `__init__.py`: 스케줄러 초기화와 시작
- `_registry.py`: 작업 탐색 및 등록
- `_lock.py`: Redis 기반 분산 락
- `inspection.py`: 스케줄러 상태 점검
- `tasks/`: 실제 정기 작업 모음

### `api/html_templates/`

Flask 렌더링용 HTML 템플릿이다.

- `landing.html`: 메인 랜딩 페이지
- `conversation.html`: 최근 대화 페이지
- `monitor.html`: 모니터링 페이지
- `scheduled_tasks.html`: 스케줄 작업 점검 페이지
- `file_delivery.html`: 파일 전달 페이지

### `api/utils/`

공통 유틸리티 영역이다.

- `utils/logger/paths.py`: 로그 경로 계산
- `utils/logger/formatters.py`: 로그 포맷 정의
- `utils/logger/service.py`: 구조화 로그 기록 기능

### `api/workflows/`

LangGraph 기반 대화 처리 계층이다.

- `lg_orchestrator.py`: Cube worker가 호출하는 실제 runtime 진입점이다.
- `registry.py`: workflow 패키지를 동적 탐색하고 `handoff_keywords`, `tool_tags`, `state_cls`를 정규화한다.
- `lg_state.py`: LangGraph에서 사용하는 `TypedDict` 상태 정의 모음이다.
- `langgraph_checkpoint.py`: thread_id 생성과 MongoDB/Memory 체크포인터 선택을 담당한다.
- `models.py`: `WorkflowReply`와 일부 레거시 호환용 dataclass를 정의한다.
- `state_service.py`: 과거 파일 기반 상태 포맷을 다루는 보조 유틸리티다. 현재 production과 devtools runner 본선은 LangGraph 체크포인터를 사용한다.

## 워크플로우 디렉터리

```text
api/workflows/
├── start_chat/
├── chart_maker/
├── translator/
└── travel_planner/
```

- `start_chat/`: 기본 진입 workflow. 일반 대화와 handoff 분기를 담당한다.
- `translator/`: 번역 workflow. 누락 슬롯 수집 후 `translate` MCP 도구를 호출한다.
- `travel_planner/`: 여행 목적지/스타일/일정을 수집하고 규칙 기반 추천을 만든다.
- `chart_maker/`: 차트 유형과 입력 데이터를 수집한 뒤 차트 스펙 스켈레톤을 만든다.

현재 본선 흐름은 모두 LangGraph 기준이다. 예전 `build_graph`/`NodeResult` 기반 구조는 일부 레거시 보조 코드에만 남아 있다.

## 메시지 플로우

### 1. Cube 수신부터 큐 적재까지

1. Cube가 `/api/v1/cube/receiver`로 POST 요청을 보낸다.
2. `api/cube/router.py`가 `accept_cube_message()`를 호출한다.
3. `accept_cube_message()`는 `extract_cube_request_fields()`로 payload를 파싱한다.
4. 빈 메시지나 wake-up 메시지면 즉시 `ignored`로 종료한다.
5. 정상 메시지는 `enqueue_incoming_message()`로 Redis 큐에 적재한다.
6. 응답은 즉시 `accepted` 또는 `duplicate`를 반환한다.

요약:

```text
Cube HTTP 요청
-> api/cube/router.receive_cube()
-> api/cube/service.accept_cube_message()
-> api/cube/payload.extract_cube_request_fields()
-> api/cube/queue.enqueue_incoming_message()
-> Cube에 accepted/duplicate 응답
```

### 2. worker 처리부터 workflow 진입까지

1. `api/cube/worker.py`가 큐에서 `CubeQueuedMessage`를 꺼낸다.
2. `process_queued_message()`가 `process_incoming_message()`를 호출한다.
3. `process_incoming_message()`는 먼저 사용자 메시지를 `conversation_service.append_message()`로 저장한다.
4. 이후 `_generate_llm_reply()`가 실제 workflow 실행을 담당한다.
5. `LLM_THINKING_MESSAGE`가 설정되어 있고 workflow 응답이 지연되면 Cube에 중간 안내 메시지를 먼저 보낸다.

요약:

```text
Redis queue
-> api/cube/worker.process_next_queued_message()
-> api/cube/service.process_queued_message()
-> api/cube/service.process_incoming_message()
-> api/conversation_service.append_message(role=user)
-> api/cube/service._generate_llm_reply()
```

### 3. LangGraph 오케스트레이션

1. `_generate_llm_reply()`는 `api/workflows/lg_orchestrator.handle_message()`를 호출한다.
2. 오케스트레이터는 `build_thread_id(user_id, channel_id)`로 LangGraph thread를 만든다.
3. `get_checkpointer()`는 MongoDB 설정이 있으면 `MongoDBSaver`, 없으면 `MemorySaver`를 사용한다.
4. 루트 그래프는 `start_chat.build_lg_graph()`를 compile한 결과다.
5. 현재 thread가 interrupt 상태면 `Command(resume=...)`로 재개하고, 아니면 새 입력으로 invoke한다.
6. 실행 결과는 `WorkflowReply(reply, workflow_id)`로 Cube 서비스 계층에 반환된다.

요약:

```text
api/cube/service._generate_llm_reply()
-> api/workflows/lg_orchestrator.handle_message()
-> api/workflows/langgraph_checkpoint.build_thread_id()
-> api/workflows/langgraph_checkpoint.get_checkpointer()
-> api/workflows/start_chat/lg_graph.build_lg_graph().compile()
-> invoke / resume
-> WorkflowReply 반환
```

### 4. `start_chat` 기본 흐름

`start_chat`은 모든 대화의 루트 workflow다.

1. `entry_node()`가 사용자 프로필을 한 번 로드한다.
2. `classify_node()`가 메시지 텍스트와 각 workflow의 `handoff_keywords`를 비교한다.
3. 번역/차트/여행 키워드가 잡히면 해당 서브그래프로 handoff한다.
4. 기본 경로면 `retrieve_context_node()`가 RAG 문맥을 만든다.
5. `generate_reply_node()`가 대화 이력을 읽고, 현재 user message를 붙여 `api.llm.service.generate_reply()`를 호출한다.

요약:

```text
start_chat.entry
-> profile.service.load_user_profile()
-> start_chat.classify
-> translator | chart_maker | travel_planner
   또는
-> start_chat.retrieve_context
-> conversation_service.get_history()
-> llm.service.generate_reply()
```

### 5. 일반 대화 응답 플로우

1. `generate_reply_node()`가 대화 이력을 읽는다.
2. 가장 마지막 항목이 이미 현재 사용자 메시지면 중복 방지를 위해 제거한다.
3. `prompt/system.py`에서 시스템 프롬프트를 만든다.
4. `llm.service._build_messages()`가 `SystemMessage + history + current HumanMessage`를 조립한다.
5. `ChatOpenAI.invoke()` 호출 결과를 `_extract_content()`로 문자열화한다.
6. 응답 문자열이 LangGraph `messages` 상태에 저장된다.

요약:

```text
conversation_service.get_history()
-> llm.prompt.get_system_prompt()
-> llm.service._build_messages()
-> ChatOpenAI.invoke()
-> llm.service._extract_content()
-> AIMessage 저장
```

### 6. 번역 workflow 플로우

1. `translator.resolve_node()`가 사용자 입력에서 원문과 목표 언어를 파싱한다.
2. 원문이 없으면 `collect_source_text_node()`가 interrupt로 재질문한다.
3. 목표 언어가 없으면 `collect_target_language_node()`가 interrupt로 재질문한다.
4. 정보가 모두 모이면 `translate_node()`가 `MCPToolCall(tool_id="translate")`를 만든다.
5. `api.mcp.executor.execute_tool_call()`이 먼저 로컬 핸들러를 찾는다.
6. 현재 번역은 `register_translator_tools()`로 등록된 로컬 `translate` 핸들러가 실행된다.
7. 번역 결과와 일본어 발음 정보가 있으면 함께 응답한다.

요약:

```text
translator.resolve
-> 부족한 슬롯 있으면 interrupt
-> translator.translate
-> mcp.executor.execute_tool_call()
-> mcp.local_tools.get_handler("translate")
-> translator.tools._translate()
-> 번역 응답 생성
```

### 7. 여행 계획 workflow 플로우

1. `travel_planner.resolve_node()`가 목적지, 스타일, 기간, 동행 정보를 규칙 기반으로 추출한다.
2. 스타일이 없으면 먼저 여행 스타일을 묻는다.
3. 목적지가 없고 스타일이 있으면 추천 후보를 제시하고 목적지를 다시 묻는다.
4. 목적지가 정해졌는데 기간이 없으면 며칠 일정인지 재질문한다.
5. 정보가 모이면 `build_plan_node()`가 추천 방문지와 일정 초안을 만든다.

요약:

```text
travel_planner.resolve
-> collect_preference (interrupt)
-> recommend_destination (interrupt)
-> collect_trip_context (interrupt)
-> build_plan
-> 여행 일정 응답 생성
```

### 8. 차트 생성 workflow 플로우

1. `entry_node()`가 원하는 차트 유형을 물어본다.
2. `collect_requirements_node()`가 차트 유형을 저장하고 입력 데이터를 물어본다.
3. `build_spec_node()`가 현재는 간단한 차트 스펙 스켈레톤을 만든다.

요약:

```text
chart_maker.entry (interrupt: 차트 유형 질문)
-> chart_maker.collect_requirements (interrupt: 데이터 질문)
-> chart_maker.build_spec
-> 차트 명세 스켈레톤 응답
```

### 9. workflow 결과부터 Cube 응답까지

1. `lg_orchestrator.handle_message()`가 `WorkflowReply`를 반환한다.
2. `process_incoming_message()`가 `send_multimessage()`로 Cube에 답변을 전송한다.
3. 성공 시 assistant 응답도 `conversation_service.append_message()`로 저장한다.
4. 응답 저장이 실패해도 사용자에게 이미 응답이 나갔다면 재전송하지 않고 로그만 남긴다.

요약:

```text
WorkflowReply
-> api/cube/service.process_incoming_message()
-> api/cube/client.send_multimessage()
-> api/conversation_service.append_message(role=assistant)
-> 처리 완료
```

## 파일 전달 플로우

메시지 플로우와 별도로 `api/file_delivery/`는 아래 경로로 동작한다.

### 업로드

```text
POST /api/v1/file-delivery/upload
-> file_delivery/router.py
-> save_uploaded_file()
-> save_file_bytes()
-> FILE_DELIVERY_STORAGE_DIR/original/<user>/<date>/... 저장
-> Redis 또는 in-memory 메타데이터 저장
-> file_url 반환
```

### 조회

```text
GET /file-delivery/files/<file_id>
-> get_file_variant()
-> 메타데이터 조회
-> 이미지면 variant 생성 또는 재사용
-> send_file() 응답
```

## 현재 구조에서 먼저 보면 좋은 파일

- `api/cube/service.py`
- `api/workflows/lg_orchestrator.py`
- `api/workflows/start_chat/lg_graph.py`
- `api/llm/service.py`
- `api/mcp/executor.py`
- `api/file_delivery/file_delivery_service.py`

## 요약

현재 본선 메시지 흐름은 `Cube -> queue -> worker -> LangGraph -> LLM/MCP -> Cube reply`로 비교적 명확하게 분리되어 있다.
메시지 입구는 `api/cube/`, 대화 판단과 분기는 `api/workflows/`, 모델 응답 생성은 `api/llm/`, 도구 호출은 `api/mcp/`, 파일 전달은 `api/file_delivery/`가 담당한다.
