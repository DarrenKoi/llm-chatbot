## 1. 진행 사항
- `gpt-oss-120b` 단일 모델 가정을 기준으로, 사용자별/채널별 모델 전환 기능의 구현 가능성과 설계 방향을 검토했다.
- `api/llm/service.py`를 확인해 현재 LLM 호출이 `config.LLM_MODEL` 단일 값에 고정되어 있음을 정리했다.
- `api/cube/service.py`, `api/workflows/lg_orchestrator.py`, `api/workflows/start_chat/lg_graph.py`를 읽고, `!model` 명령은 일반 대화 전에 가로채는 제어 명령 경로로 처리하는 방향을 제안했다.
- `api/workflows/langgraph_checkpoint.py`, `api/workflows/lg_state.py`, `api/workflows/state_service.py`를 검토해 모델 선택 상태는 전역 설정 변경이 아니라 `user_id + channel_id` 기준의 thread/channel 범위 선호값으로 저장하는 것이 안전하다고 정리했다.
- 사용자 UX 측면에서 `!model`, `!model list`, `!model current`, `!model <alias>`, `!model reset` 형태를 제안했고, 자연어 문의는 목록 안내까지 허용하되 실제 전환은 명시 명령 또는 확인 절차를 거치도록 권장했다.

## 2. 수정 내용
- 코드 수정은 수행하지 않았고, 구현 계획만 정리했다.
- 신규 생성 파일 경로: `doc/journals/260407/260407_212211-model-switch-planning.md`
- 설계 검토에 사용한 주요 파일 경로:
  - `api/llm/service.py`
  - `api/cube/service.py`
  - `api/workflows/lg_orchestrator.py`
  - `api/workflows/start_chat/lg_graph.py`
  - `api/workflows/langgraph_checkpoint.py`
  - `api/workflows/lg_state.py`
  - `api/workflows/state_service.py`
  - `tests/test_llm_service.py`
  - `tests/test_cube_service.py`

## 3. 다음 단계
- 서버 내부에 공개 alias와 비공개 upstream 설정을 분리한 모델 레지스트리 모듈을 추가한다.
- `user_id + channel_id` 기준의 모델 선호 저장소를 만들고, 조회 우선순위를 `thread/channel -> user default(선택) -> system default`로 정의한다.
- `api/cube/service.py`에 `!model` 제어 명령 인터셉터를 추가해 일반 대화 이력에 명령 문자열이 섞이지 않도록 한다.
- `api/llm/service.py`를 리팩터링해 요청 시점에 선택된 모델 alias를 해석하고, 해당 provider/base URL/API key로 클라이언트를 생성하도록 바꾼다.
- `api/workflows/start_chat/lg_graph.py`에서 현재 모델과 제공 가능한 모델 목록을 안내할 수 있도록 런타임 컨텍스트 주입 방식을 정리한다.
- 실패 시 이전 모델 유지, 비활성 모델 차단, 잘못된 alias 검증, 재시도 중복 처리 같은 운영 안전장치를 테스트 케이스로 추가한다.

## 4. 메모리 업데이트
- 변경 없음
