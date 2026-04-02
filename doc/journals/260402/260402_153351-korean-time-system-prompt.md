## 1. 진행 사항
- `api/llm/prompt/system.py`에서 시스템 프롬프트를 요청 시점에 동적으로 생성하도록 변경하고, `Asia/Seoul` 기준 현재 시각을 포함하도록 구성했다.
- 사용자가 현재 시간이나 날짜를 물으면 시스템 프롬프트에 포함된 한국 현지 시각을 기준으로 답하도록 지시 문구를 추가했다.
- `api/config.py`에 `LLM_TIMEZONE` 환경변수를 추가해 기본값을 `Asia/Seoul`로 설정했다.
- `tests/test_llm_service.py`, `tests/test_http_clients.py`를 갱신해 시간 문맥 생성과 LLM 요청 payload 구성을 검증했다.
- `pytest tests/test_llm_service.py tests/test_http_clients.py -v`를 실행해 11개 테스트 통과를 확인했다.

## 2. 수정 내용
- 수정 파일: `api/config.py`
  - `LLM_TIMEZONE` 설정 추가.
- 수정 파일: `api/llm/prompt/system.py`
  - `get_system_prompt()`가 기본/override 프롬프트 뒤에 한국 현지 시각 문맥을 붙이도록 변경.
  - `_build_time_context()`와 `_get_llm_timezone()` 추가.
- 수정 파일: `tests/test_llm_service.py`
  - 시스템 프롬프트가 시간 문맥을 포함하는지 검증하도록 테스트 수정.
  - UTC 입력이 `Asia/Seoul` 시각으로 변환되는지 검증하는 테스트 추가.
- 수정 파일: `tests/test_http_clients.py`
  - 동적 시스템 프롬프트를 고려해 `api.llm.service.get_system_prompt`를 mock 하도록 테스트 안정화.

## 3. 다음 단계
- 실제 연동 환경에서 사용자가 `지금 몇 시야?`, `오늘 날짜가 뭐야?`처럼 질문했을 때 한국 시각으로 응답하는지 확인.
- 운영 프롬프트 override를 사용하는 배포 환경이 있다면 `LLM_TIMEZONE` 기본값 또는 override 프롬프트와의 조합을 한 번 점검.

## 4. 메모리 업데이트
- 변경 없음
