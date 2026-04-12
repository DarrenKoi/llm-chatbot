# MongoDB + LangGraph + Devtools 통합 점검

## 1. 진행 사항

MongoDB가 LangGraph 체크포인터 및 대화 이력 저장소로 Cube 플랫폼에서 올바르게 동작하는지 점검하고,
devtools가 Cube/MongoDB/Redis 없이 동료 개발자가 독립적으로 사용할 수 있는지 확인했다.

4개 리뷰 에이전트(코드 재사용, 코드 품질, 효율성, MongoDB+LangGraph+Devtools 전용)를 병렬 실행하여
코드베이스 전반을 점검하고, 발견된 크리티컬 이슈를 수정했다.

## 2. 발견 사항

### 크리티컬 — 수정 완료

| 이슈 | 파일 | 설명 |
|------|------|------|
| MongoClient 미캐싱 | `api/workflows/langgraph_checkpoint.py` | `get_checkpointer()` 호출 시마다 새 `MongoClient`를 생성하고 `ping`을 실행. `_compiled_graph` 싱글톤으로 현재 1회 호출로 제한되지만, 직접 재사용 시 커넥션 누수 발생. |
| 워커당 2개 MongoClient | `conversation_service.py` + `langgraph_checkpoint.py` | 동일 MongoDB에 독립적 커넥션 풀 2개 생성. uWSGI N개 워커 기준 2N개 커넥션 풀 유지. |

**수정**: `api/mongo.py`에 캐싱 팩토리(`get_mongo_client()`)를 생성하고, `langgraph_checkpoint.py`와 `conversation_service.py`가 공유 클라이언트를 사용하도록 변경. 워커당 커넥션 풀 2N → N으로 절감.

### 보통 — 인지 필요

| 이슈 | 파일 | 설명 |
|------|------|------|
| TTL 인덱스 변경 불가 | `conversation_service.py` | `CONVERSATION_TTL_SECONDS` 값을 변경해도 기존 MongoDB TTL 인덱스는 자동 갱신되지 않음. 수동으로 인덱스를 drop 후 재생성해야 함. |
| `CONVERSATION_TTL_SECONDS` 기본값 0 | `config.py` | 대화 이력 문서가 만료되지 않고 영구 축적. `CHECKPOINT_TTL_SECONDS`(3일)와 정책 차이 존재. 의도적이라면 무방. |
| lg_adapter 중복 | `translator/lg_adapter.py`, `chart_maker/lg_adapter.py` | `_get_graph()` + `_run_lg_node()` 동일 패턴 복사. Phase 4 클린업 시 통합 대상. |
| `cube/service.py` log_activity 반복 | `api/cube/service.py` | 동일 kwargs(`user_id`, `user_name`, `channel_id`, `message_id`) 17회 반복. 헬퍼 추출 가능. |
| `double get_state()` | `lg_orchestrator.py` L39, L54 | invoke 전 interrupt 확인 + invoke 후 결과 조회. LangGraph 설계상 필수. 버그 아님. |

### 낮음 — 참고

- 글로벌 싱글톤 7개 파일에 반복 (테스트 리셋 어려움)
- `NodeAction` 문자열 비교 — enum/상수 미사용
- `_InMemoryBackend._recent_messages` — `_store`와 중복 데이터
- `_LocalFileBackend._is_duplicate` — 파일 전체 O(n) 스캔 (devtools 전용이라 영향 적음)

## 3. Devtools 독립성 점검 결과

| 항목 | 결과 |
|------|------|
| Cube 없이 실행 가능? | O — `devtools/workflow_runner/app.py`가 독립 Flask 서버(port 5001) 실행 |
| MongoDB 없이 실행 가능? | O — `_configure_dev_runtime()`이 `CONVERSATION_BACKEND="local"` 설정 |
| Redis 없이 실행 가능? | O — conversation은 로컬 파일, workflow state는 JSON 파일 |
| LangGraph 없이 실행 가능? | O — devtools는 기존 커스텀 그래프 시스템(`NodeResult`/`WorkflowState`/`build_graph`) 사용 |

**주의**: devtools는 **기존 커스텀 그래프 엔진**을 사용하고, production은 **LangGraph StateGraph** 기반이다.
Phase 4 클린업이 완료되면 devtools도 LangGraph로 이관하거나, 두 시스템의 차이를 명확히 문서화해야 한다.
동료가 devtools에서 개발한 워크플로를 production에 승격할 때, `NodeResult` → `LangGraph 노드 함수` 변환이 필요하다.

## 4. 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `api/mongo.py` (신규) | 캐싱 MongoClient 팩토리 |
| `api/workflows/langgraph_checkpoint.py` | `get_mongo_client()` 사용으로 전환 |
| `api/conversation_service.py` | `get_mongo_client()` 사용으로 전환 |
| `tests/test_langgraph_checkpoint.py` | mock 대상을 `api.mongo.get_mongo_client`로 변경 |
| `tests/test_conversation_service.py` | mock 대상을 `api.mongo.get_mongo_client`로 변경 |

## 5. 기존 테스트 실패 발견

`tests/test_file_delivery_routes.py::test_file_delivery_upload_invalid_extension` — `txt`가 허용 확장자에 추가되었으나 테스트가 갱신되지 않음. 이번 수정과 무관.

## 6. 다음 단계

- Phase 4 클린업 진행 시 devtools의 LangGraph 이관 여부 결정
- `CONVERSATION_TTL_SECONDS` 운영 정책 확인 (영구 보관 의도인지)
- TTL 인덱스 변경 절차 문서화 (MongoDB에서 수동 drop 필요)
- `test_file_delivery_upload_invalid_extension` 테스트 수정
