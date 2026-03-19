# Cube 웨이크업 메시지 필터링 & 로그 정리

**날짜**: 2026-03-19
**세션 주제**: Cube 챗봇 웨이크업 메시지가 대화 히스토리에 저장되는 버그 수정 + activity.jsonl 로그 필드 정리

---

## 1. 진행 사항

- Cube 챗봇이 대화를 이어갈수록 LLM이 응답을 멈추는 문제 원인 분석
  - `message_id="-1"`, 메시지 내용 `!@#`로 시작하는 웨이크업 신호가 대화 히스토리에 저장되고 LLM에 전송되고 있었음
  - `CONVERSATION_MAX_MESSAGES=20` 제한 내에서 웨이크업 메시지가 실제 대화를 밀어내며 LLM 응답 품질 저하 유발
- 웨이크업 메시지 필터링 로직 구현 (히스토리 저장 X, LLM 전송 X, Cube 응답 X)
- activity.jsonl 로그 포맷에서 `@timestamp`, `environment` 필드 제거 요청 반영

## 2. 수정 내용

### `api/cube/service.py`
- `_WAKEUP_MESSAGE_ID = "-1"`, `_WAKEUP_PREFIX = "!@#"` 상수 추가
- `_is_wakeup_message()` 함수 추가 — `message_id`와 메시지 접두사 기반 판별
- `handle_cube_message()` 상단에서 웨이크업 감지 시 early return (silent, 빈 `llm_reply` 반환)
- `cube_wakeup_skipped` 활동 로그 기록

### `api/utils/logger/formatters.py`
- `build_log_document()` 에서 `@timestamp` 필드 제거 (단일 `timestamp`만 유지)
- `environment` 필드 제거

### `tests/test_cube_service.py`
- `test_wakeup_message_skips_history_and_llm` 테스트 추가
- 웨이크업 메시지 시 `get_history`, `append_message`, `generate_reply`, `send_multimessage` 모두 미호출 검증

### `tests/test_logger_utils.py`
- `@timestamp` 미존재, `environment` 미존재 단언으로 변경

## 3. 다음 단계

- 사무실 환경에서 실제 Cube 웨이크업 메시지로 동작 확인
- `test_main_page.py::test_main_page_renders_sample_template` 테스트 실패 — 템플릿이 변경되어 `"Flask Sample Template"` 문자열이 없음 (기존 이슈, 이번 세션과 무관)

## 4. 메모리 업데이트

변경 없음
