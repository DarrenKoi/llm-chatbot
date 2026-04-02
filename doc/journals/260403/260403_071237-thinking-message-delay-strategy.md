## 1. 진행 사항
- `api/config.py`에서 `LLM_THINKING_MESSAGE` 기본값이 `잠시만요, 답변을 준비하고 있어요... 🤔`로 고정되어 있음을 확인했다.
- `api/cube/service.py`의 `handle_cube_message()`에서 실제 LLM 응답 생성 전에 `send_multimessage(..., reply_message=config.LLM_THINKING_MESSAGE)`를 항상 먼저 호출하는 흐름을 확인했다.
- `tests/test_cube_service.py`에서 thinking message가 LLM 호출 전에 전송되는 현재 동작을 테스트로 고정하고 있음을 확인했다.
- 사용자의 우려 사항을 기준으로, 빠른 응답에는 중간 안내 문구를 생략하고 지연 시에만 노출하는 방향이 더 자연스럽다는 해결안을 정리했다.
- 위 조사 결과와 개선 방향을 `doc/journals/260403/260403_071237-thinking-message-delay-strategy.md`로 기록했다.

## 2. 수정 내용
- 생성 파일: `doc/journals/260403/260403_071237-thinking-message-delay-strategy.md`
  - 사용자가 느낀 부자연스러운 응답 경험의 원인을 현재 코드 기준으로 정리했다.
  - 해결 방향으로 "항상 선행 전송" 대신 "지연 임계치 기반 조건부 전송" 전략을 문서화했다.
- 애플리케이션 코드 수정은 없었다.

## 3. 다음 단계
- `api/cube/service.py`에서 thinking message를 즉시 전송하지 말고, 예를 들어 1.5초에서 2초 이상 응답이 지연될 때만 보내도록 구조를 바꾸기.
- 가능하면 LLM 호출과 지연 타이머를 분리해, 응답이 임계치 전에 완료되면 안내 문구를 보내지 않도록 처리하기.
- `api/config.py`에 `LLM_THINKING_MESSAGE_DELAY_SECONDS` 같은 환경변수를 추가해 운영 환경에서 임계치를 조정할 수 있게 만들기.
- `tests/test_cube_service.py`를 갱신해 "빠른 응답에서는 안내 문구 없음", "느린 응답에서만 안내 문구 전송" 시나리오를 검증하기.

## 4. 메모리 업데이트
- 변경 없음
