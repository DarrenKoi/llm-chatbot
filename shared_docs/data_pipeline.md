# 데이터 파이프라인 가이드

이 문서는 사용자의 메시지가 들어온 뒤 어떤 경로를 거쳐 응답이 생성되고 저장되는지 설명합니다.

## 전체 흐름

```text
Cube 요청
  -> api/cube/router.py
  -> api/cube/service.accept_cube_message()
  -> api/cube/queue.py
  -> api/cube/worker.py
  -> api/cube/service.process_incoming_message()
  -> api/workflows/lg_orchestrator.py
  -> api/workflows/start_chat 또는 서브워크플로
  -> api/cube/client.py
  -> Cube 응답 전송
```

## 1. 요청 수신 단계

- Cube는 `/api/v1/cube/receiver`로 메시지를 전송합니다.
- `api/cube/router.py`는 요청 JSON을 받아 `accept_cube_message()`로 넘깁니다.
- 이 단계에서는 메시지를 바로 처리하지 않고 먼저 큐 적재 가능 여부를 확인합니다.

## 2. 입력 검증과 큐 적재 단계

- `api/cube/service.py`의 `_parse_incoming_message()`는 `user_id`, `channel_id`, `message_id`, `message`를 정리합니다.
- 빈 메시지나 wake-up 이벤트는 워크플로로 넘기지 않고 무시합니다.
- 정상 메시지는 `enqueue_incoming_message()`를 통해 큐에 적재합니다.
- 이 구조 덕분에 HTTP 응답과 실제 워크플로 처리 시간을 분리할 수 있습니다.

## 3. 워커 소비 단계

- `cube_worker.py` 또는 `api/cube/worker.py`가 큐에서 메시지를 하나씩 가져옵니다.
- 워커는 실패 시 재시도 횟수를 관리하고, 최종 실패 시 에러 로그를 남깁니다.
- 메시지가 정상 처리되면 큐에서 acknowledge 처리합니다.

## 4. 대화 이력 저장 단계

- `process_incoming_message()`는 워크플로 실행 전에 사용자 발화를 `conversation_service.append_message()`로 저장합니다.
- 저장 메타데이터에는 `channel_id`, `message_id`, `direction`, `source` 같은 정보가 포함됩니다.
- 이 단계가 먼저 수행되기 때문에 이후 응답 생성 실패가 발생해도 입력 이력은 남길 수 있습니다.

## 5. 워크플로 실행 단계

- `api/workflows/lg_orchestrator.py`의 `handle_message()`가 실제 LangGraph 실행 진입점입니다.
- thread id는 `user_id::channel_id` 형태로 생성합니다.
- 같은 사용자와 같은 채널의 후속 메시지는 같은 thread를 이어서 사용합니다.
- 이미 interrupt 상태가 있으면 `Command(resume=...)`로 재개합니다.
- interrupt 상태가 없으면 `start_chat` 워크플로로 새 입력을 넣어 실행합니다.

## 6. 라우팅과 서브워크플로 단계

- `api/workflows/start_chat/lg_graph.py`가 기본 루트 그래프입니다.
- `classify_node`는 현재 메시지와 `handoff_keywords`를 비교해 의도를 결정합니다.
- 일반 대화는 `retrieve_context -> generate_reply` 경로로 처리합니다.
- 특정 업무 키워드가 감지되면 `translator`, `travel_planner`, `chart_maker` 같은 서브워크플로로 넘깁니다.

## 7. 컨텍스트 수집 단계

- 일반 대화에서는 `retrieve_context_node()`가 RAG 문서를 조회합니다.
- `generate_reply_node()`는 대화 이력, 검색 컨텍스트, 사용자 프로필, 파일 목록을 합쳐 LLM 입력을 구성합니다.
- 파일 목록은 `api/file_delivery/`에서 사용자별 파일 메타데이터를 읽어 컨텍스트 문자열로 변환합니다.

## 8. 응답 생성 단계

- 일반 대화 응답은 `api/llm/service.py`의 `generate_reply()`를 통해 생성합니다.
- 업무형 워크플로는 각 서브그래프 내부 노드에서 필요한 도구 호출이나 상태 전이를 수행합니다.
- 추가 정보가 필요한 경우 LangGraph `interrupt()`로 사용자 입력을 다시 요청합니다.

## 9. 응답 전송 단계

- 워크플로가 반환한 텍스트는 `plan_delivery()`를 거쳐 전송 단위로 분할될 수 있습니다.
- 일반 텍스트는 `send_multimessage()`로 전송합니다.
- 리치 알림이 필요한 경우 `send_richnotification()`으로 전송합니다.
- Cube 전송 실패는 `CubeUpstreamError`로 처리하며 재시도 또는 실패 로그로 이어집니다.

## 10. 출력 이력 저장 단계

- 응답 전송이 끝나면 assistant 메시지를 다시 `conversation_service.append_message()`로 저장합니다.
- 이때 `reply_to_message_id`와 `workflow_id`를 메타데이터에 함께 남깁니다.
- 응답은 이미 사용자에게 전달된 뒤이므로, 저장 실패가 나더라도 예외를 다시 올리지는 않습니다.

## 11. 로깅과 추적 단계

- 각 단계는 `log_activity()`와 `log_request()`를 통해 활동 로그를 남깁니다.
- 큐 적재, 워커 재시도, 응답 생성, 응답 전송, 저장 실패 같은 이벤트가 모두 구조화된 로그로 기록됩니다.
- 워크플로 등록 정보도 `api/workflows/registry.py`에서 별도 워크플로 로그로 남깁니다.

## 개발 환경에서의 차이점

- 운영 경로는 `api/workflows/`를 사용합니다.
- 개발 검증 경로는 `devtools/workflow_runner/`와 `devtools/workflows/`를 사용합니다.
- dev runner는 운영 대화 이력 대신 `devtools/var/conversation_history/`를 사용합니다.
- dev runner는 워크플로별 `MemorySaver`를 사용하므로 운영 데이터와 섞이지 않습니다.

## 팀원이 파이프라인을 볼 때 집중할 위치

1. 요청 수신은 `api/cube/router.py`와 `api/cube/service.py`를 봅니다.
2. 비동기 처리와 재시도는 `api/cube/worker.py`를 봅니다.
3. 워크플로 진입은 `api/workflows/lg_orchestrator.py`를 봅니다.
4. 일반 대화와 업무 분기는 `api/workflows/start_chat/lg_graph.py`를 봅니다.
5. 실제 업무 로직은 각 서브워크플로 패키지를 봅니다.

이 파이프라인을 기준으로 보면 저장소 전체 구조가 훨씬 자연스럽게 연결됩니다.
