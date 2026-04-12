## 1. 진행 사항
- `translator` 워크플로를 LLM 결정형 구조로 변경했다. `api/workflows/translator/llm_decision.py`를 추가해 `translate / ask_user / end_conversation`를 JSON으로 판단하도록 구성했다.
- `travel_planner` 워크플로를 LLM 결정형 구조로 변경했다. `api/workflows/travel_planner/llm_decision.py`를 추가해 `ask_user / recommend_destination / build_plan / end_conversation`를 JSON으로 판단하도록 구성했다.
- `api`와 `devtools`의 translator/travel_planner 노드가 동일한 LLM 결정 모듈을 공용으로 사용하도록 정리했다.
- `api/llm/service.py`에 `generate_json_reply()`를 추가해 workflow controller가 현재 `LLM_MODEL`로 JSON 객체를 요청하고 파싱할 수 있게 했다.
- `tests/test_llm_service.py`, `tests/test_workflow_llm_decision.py`, `tests/test_translator_lg_graph.py`, `tests/test_travel_planner_lg_graph.py`, `tests/test_devtools_workflow_examples.py`, `tests/test_start_chat_lg_graph.py` 범위로 회귀를 확인했다.

## 2. 수정 내용
- `api/llm/service.py`
  - LLM JSON 응답 호출 함수 `generate_json_reply()` 추가
  - fenced JSON / 본문 내 JSON object 파싱 로직 추가
- `api/llm/__init__.py`
  - `generate_json_reply` export 추가
- `api/workflows/translator/llm_decision.py`
  - 번역 워크플로용 LLM 판단 모듈 추가
  - LLM 실패 시 규칙 기반 fallback 유지
- `api/workflows/translator/nodes.py`
  - regex 중심 분기 대신 `decide_translation_turn()` 결과를 사용하도록 변경
- `api/workflows/translator/lg_graph.py`
  - LangGraph `resolve_node()`가 LLM 판단 결과를 사용하도록 변경
  - interrupt reply를 `pending_reply` 상태로 전달하도록 변경
- `api/workflows/travel_planner/llm_decision.py`
  - 여행 계획 워크플로용 LLM 판단 모듈 추가
- `api/workflows/travel_planner/nodes.py`
  - `decide_travel_planner_turn()` 기반으로 `wait / recommend / build / end` 분기 변경
- `api/workflows/travel_planner/lg_graph.py`
  - LangGraph `resolve_node()`에서 LLM 판단 결과를 사용하도록 변경
- `api/workflows/lg_state.py`
  - LangGraph 상태에 `pending_reply` 필드 추가
- `devtools/workflows/translator_example/nodes.py`
  - production과 같은 번역 LLM 결정 모듈 재사용
- `devtools/workflows/travel_planner_example/nodes.py`
  - production과 같은 여행 계획 LLM 결정 모듈 재사용
- `tests/test_llm_service.py`
  - JSON reply parsing 테스트 추가
- `tests/test_workflow_llm_decision.py`
  - workflow decision helper 단위 테스트 추가

실행한 검증 명령:
- `uv run pytest tests/test_llm_service.py tests/test_workflow_llm_decision.py tests/test_translator_lg_graph.py tests/test_travel_planner_lg_graph.py tests/test_devtools_workflow_examples.py tests/test_start_chat_lg_graph.py -q`
- 결과: `37 passed, 1 warning`

## 3. 다음 단계
- 실제 사내 LLM endpoint 환경에서 translator/travel_planner가 기대한 JSON 형식으로 안정적으로 응답하는지 smoke test가 필요하다.
- `chart_maker`와 이후 추가되는 workflow도 같은 패턴으로 `LLM decision layer + deterministic execution` 구조를 적용할지 검토가 필요하다.
- workflow controller용 프롬프트를 별도 파일로 분리할지, 현재처럼 결정 모듈 내부 상수로 둘지 정리할 필요가 있다.

## 4. 메모리 업데이트
- `MEMORY.md`에 workflow 결정 패턴 섹션을 추가했다.
- 핵심 내용: workflow는 LLM으로 액션을 판단하고, 실제 실행은 결정적 코드 경로로 유지하며, 실패 시 fallback 규칙으로 복구한다.
