## 1. 진행 사항
- 사용자가 Cube 대화 중 `잠시만요, 답변을 준비하고 있어요` 문구가 모든 응답마다 보여 부자연스럽다고 느끼는 문제를 검토했다.
- `api/config.py`와 `api/cube/service.py`를 확인해, 기존에는 `handle_workflow_message()` 호출 전에 `LLM_THINKING_MESSAGE`를 항상 먼저 전송하는 구조였음을 확인했다.
- `api/cube/service.py`의 `process_incoming_message()` 흐름을 수정해, LLM 응답 생성 작업을 먼저 시작하고 지정한 지연 시간 안에 응답이 오면 최종 답변만 보내도록 변경했다.
- 응답이 지연될 때만 안내 문구를 보내도록 `_send_thinking_message()`와 `_generate_llm_reply()` helper를 추가했다.
- `api/config.py`에 `LLM_THINKING_MESSAGE_DELAY_SECONDS` 설정을 추가하고, 사용자 요청에 맞춰 기본값을 `5`초로 조정했다.
- `tests/test_cube_service.py`를 갱신해 빠른 응답에서는 안내 문구가 생략되고, 느린 응답 또는 느린 실패에서만 안내 문구가 전송되는지 검증했다.
- `python3 -m pytest tests/test_cube_service.py -v`, `python3 -m pytest tests/ -v`, `python3 -m pytest tests/test_config.py tests/test_cube_service.py -v`를 실행해 통과를 확인했다.
- 관련 변경을 `efa6a32`, `0dea5c0`, `aa432a2` 커밋으로 정리하고 `main` 브랜치에 푸시했다.

## 2. 수정 내용
- 수정 파일: `api/config.py`
  - `LLM_THINKING_MESSAGE_DELAY_SECONDS` 환경변수를 추가했다.
  - 기본 지연 시간을 `5`초로 설정했다.
- 수정 파일: `api/cube/service.py`
  - `ThreadPoolExecutor` 기반으로 LLM 응답을 먼저 시작한 뒤, 지연 임계치 초과 시에만 thinking message를 보내도록 변경했다.
  - `_send_thinking_message()`와 `_generate_llm_reply()`를 추가했다.
- 수정 파일: `tests/test_cube_service.py`
  - 빠른 응답에서는 안내 문구가 전송되지 않는 테스트를 추가했다.
  - 느린 응답과 느린 실패에서만 안내 문구가 전송되는 테스트를 추가했다.
- 수정 파일: `MEMORY.md`
  - Cube 응답 대기 문구는 `LLM_THINKING_MESSAGE_DELAY_SECONDS` 초과 시에만 전송되고, 현재 기본값은 `5`초라는 운영 규칙을 추가했다.
- 생성 파일: `doc/journals/260403/260403_072644-cube-thinking-message-fix.md`
  - 이번 세션의 문제 인식, 수정 내용, 검증 결과, 메모리 업데이트를 기록했다.

## 3. 다음 단계
- 운영 `.env`에 별도 `LLM_THINKING_MESSAGE_DELAY_SECONDS` 값이 설정돼 있다면 현재 기본값 `5`초와 충돌하지 않는지 확인하기.
- 실제 Cube 연동 환경에서 5초 이하 응답에는 안내 문구가 나오지 않고, 5초 초과 응답에서만 안내 문구가 보이는지 체감 검증하기.
- 필요하면 `LLM_THINKING_MESSAGE` 자체 문구도 더 자연스러운 표현으로 조정하기.

## 4. 메모리 업데이트
- `MEMORY.md`의 `Cube 수신 처리 규칙` 섹션에 응답 대기 안내 문구가 지연 조건부로만 전송되며 현재 기본 지연 시간이 `5`초라는 내용을 추가했다.
