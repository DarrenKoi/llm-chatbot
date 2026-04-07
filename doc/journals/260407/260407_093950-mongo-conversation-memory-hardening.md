## 1. 진행 사항
- `api/conversation_service.py`의 MongoDB 대화 저장소를 점검하고, 대화 이력이 `user_id` 단위로만 섞이던 구조를 `conversation_id` 기준으로 분리되도록 수정했다.
- `api/cube/service.py`에서 Cube 수신/응답 메시지 저장 흐름을 점검하고, 사용자 메시지는 응답 생성 전에 저장하고 assistant 메시지는 실제 전송 성공 후 저장하도록 순서를 조정했다.
- `api/workflows/orchestrator.py`, `api/workflows/state_service.py`, `api/workflows/models.py`를 수정해 워크플로 상태 파일도 `channel_id` 기준으로 분리 저장되도록 정리했다.
- `api/workflows/start_chat/agent/executor.py`에서 LLM 프롬프트에 넣는 history 조회를 현재 채널 기준으로 제한했다.
- `.env.example`, `api/config.py`에서 `CONVERSATION_MAX_MESSAGES` 기본값을 5로 맞췄다.
- `pytest tests/test_conversation_service.py tests/test_cube_service.py tests/test_start_chat_workflow.py tests/test_llm_service.py tests/test_monitoring_service.py tests/test_monitor_page.py -q`를 실행해 52개 테스트가 통과하는 것을 확인했다.

## 2. 수정 내용
- 변경 파일:
  `/.env.example`
  `/api/config.py`
  `/api/conversation_service.py`
  `/api/cube/service.py`
  `/api/monitoring_service.py`
  `/api/workflows/models.py`
  `/api/workflows/orchestrator.py`
  `/api/workflows/start_chat/agent/executor.py`
  `/api/workflows/state_service.py`
  `/tests/test_conversation_service.py`
  `/tests/test_cube_service.py`
  `/tests/test_start_chat_workflow.py`
  `/doc/journals/260407/260407_093950-mongo-conversation-memory-hardening.md`
- `api/conversation_service.py`에 `ConversationStoreError`를 추가했다. `AFM_MONGO_URI`가 설정된 상태에서 MongoDB 연결이 실패하면 더 이상 조용히 in-memory fallback 하지 않고 명시적으로 오류를 내도록 바꿨다.
- MongoDB 문서 구조에 `conversation_id`와 선택적 메타데이터(`message_id`, `channel_id`, `direction`, `reply_to_message_id`, `user_name`, `source`)를 담도록 정리했다.
- MongoDB 인덱스를 `(user_id, conversation_id, created_at)` 조회 인덱스, `created_at` TTL 인덱스, `message_id` 기반 중복 방지 인덱스로 보강했다.
- `api/cube/service.py`에서 `get_history()`와 `append_message()` 호출 시 `conversation_id=incoming.channel_id`를 사용하도록 수정했다.
- `api/monitoring_service.py`에서 MongoDB ping 실패 시 더 이상 fallback 상태가 아니라 오류 상태로 보이도록 정정했다.
- 테스트는 채널별 history 분리, Mongo 문서 메타데이터, strict Mongo 동작, 채널별 workflow state 저장을 기준으로 업데이트했다.

## 3. 다음 단계
- 실제 로컬/운영 MongoDB에서 `cube_conversation_messages` 컬렉션 인덱스가 의도한 형태로 생성되는지 확인한다.
- 기존 user-only workflow state 파일이 남아 있다면 채널별 상태 파일로 자연스럽게 전환되는지 점검하고 필요하면 정리 스크립트를 추가한다.
- 실제 환경 변수에서 `CONVERSATION_MAX_MESSAGES=5`와 `CONVERSATION_TTL_SECONDS` 값이 현재 운영 의도와 맞는지 확인한다.

## 4. 메모리 업데이트
- 변경 없음
