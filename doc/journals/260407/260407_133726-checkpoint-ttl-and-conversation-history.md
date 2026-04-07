## 1. 진행 사항
- `api/workflows/langgraph_checkpoint.py`의 `get_checkpointer()`를 점검해 MongoDB 기반 LangGraph 체크포인터가 `MongoDBSaver`의 TTL 옵션을 직접 사용하도록 정리했다.
- `api/config.py`와 `.env.example`에 `CHECKPOINT_TTL_SECONDS`, `CONVERSATION_COLLECTION_NAME`, `LANGGRAPH_CHECKPOINT_COLLECTION_NAME`, `LANGGRAPH_CHECKPOINT_WRITES_COLLECTION_NAME` 설정을 추가했다.
- `api/conversation_service.py`를 검토하고 대화 이력 컬렉션 기본값을 `conversation_history`로 분리했으며, 기본 TTL을 비활성화해 영구 보관 정책으로 맞췄다.
- `tests/test_langgraph_checkpoint.py`, `tests/test_conversation_service.py`, `tests/test_config.py`를 보강해 체크포인트 TTL, 컬렉션 이름 분리, 대화 이력 TTL 비활성화 동작을 검증했다.
- `pytest tests/test_langgraph_checkpoint.py tests/test_conversation_service.py tests/test_config.py -q`와 `pytest tests/test_lg_orchestrator.py tests/test_cube_service.py -q`를 실행해 변경 범위 스모크 테스트를 확인했다.
- LangGraph 마이그레이션 구조를 다시 리뷰해 체크포인터와 감사용 대화 이력 저장소의 역할 분리는 맞아졌는지 재점검했다.

## 2. 수정 내용
- 변경 파일:
  `api/config.py`
  `.env.example`
  `api/workflows/langgraph_checkpoint.py`
  `api/conversation_service.py`
  `tests/test_langgraph_checkpoint.py`
  `tests/test_conversation_service.py`
  `tests/test_config.py`
  `MEMORY.md`
- `api/workflows/langgraph_checkpoint.py`에서 Mongo 연결 후 `ping`을 수행하고, `MongoDBSaver(..., ttl=config.CHECKPOINT_TTL_SECONDS)` 형태로 3일 TTL을 주입하도록 수정했다.
- `api/conversation_service.py`의 Mongo 컬렉션명을 하드코딩 `cube_conversation_messages`에서 설정 기반 `conversation_history`로 변경했다.
- 대화 이력 기본 TTL을 `CONVERSATION_TTL_SECONDS=0`으로 바꿔 별도 감사 저장소가 기본적으로 만료되지 않도록 조정했다.
- `MEMORY.md`에 LangGraph 체크포인트와 대화 이력 컬렉션의 책임 분리 규칙을 기록했다.

## 3. 다음 단계
- `api/workflows/lg_orchestrator.py`와 각 `lg_graph.py`에서 LangGraph `messages`가 실제 사용자/어시스턴트 대화를 완전하게 누적하는지 정리한다.
- `api/workflows/start_chat/lg_graph.py`가 `conversation_service.get_history()` 대신 체크포인트 기반 `messages`를 주 컨텍스트로 쓰도록 정리할지 결정한다.
- `api/workflows/chart_maker/lg_graph.py`의 빈 `interrupt({"reply": ""})` 응답을 사용자 메시지로 교체해 첫 턴 응답 품질을 보완한다.

## 4. 메모리 업데이트
- `MEMORY.md`에 LangGraph 체크포인트 3일 TTL, `conversation_history` 영구 보관, 단기 상태와 감사 저장소의 역할 분리 규칙을 추가했다.
