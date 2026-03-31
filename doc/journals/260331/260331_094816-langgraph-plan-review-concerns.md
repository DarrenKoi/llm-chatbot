## 1. 진행 사항
- `doc/랭그래프_api_구조_계획.md`를 검토하고 현재 구현(`api/cube/service.py`, `api/conversation_service.py`, `api/__init__.py`)과 맞지 않을 수 있는 설계 우려를 정리했다.
- 사용자 추가 설명을 반영해 `remove` 명령은 이후 `remove --recent`, `remove --all` 같은 형태로 구체화될 예정임을 확인했다.
- 사용자 추가 설명을 반영해 모델 변경 범위는 "사용자 + 사용자가 현재 속한 채널" 단위임을 확인했다.
- 위 내용을 바탕으로 이후 문서 보완이 필요한 핵심 쟁점을 저널 파일로 기록했다.

## 2. 수정 내용
- 새 파일 생성: `doc/journals/260331/260331_094816-langgraph-plan-review-concerns.md`
- 코드 수정은 없었고, 계획 문서 리뷰 결과와 남은 설계 우려만 기록했다.
- 현재 남아 있는 주요 우려:
  - 대화/체크포인터 키를 `user_id` 단독으로 둘지, `user_id + channel_id` 조합으로 둘지 명확히 정의가 필요하다.
  - `chat/service.py`가 단순 reply 문자열만 반환하면 `model_used`, `tool_calls`, `thread_id`, archive용 메타데이터를 상위 계층에서 다루기 어렵다.
  - `conversation_service.py` 제거 시 현재 `/` 화면에서 사용하는 최근 대화 조회 read model과 Mongo 장애 시 fallback 책임을 어디서 맡을지 정해야 한다.
  - 아카이빙을 응답 후 비동기로 분리할 경우 현재 큐 재시도 구조와 맞물린 idempotency/outbox 전략이 필요하다.

## 3. 다음 단계
- `doc/랭그래프_api_구조_계획.md`에 모델 범위를 `user_id + channel_id` 기준으로 명시한다.
- `remove` 명령이 구체화되면 삭제 범위별로 checkpointer, archive, 운영 화면 반영 범위를 함께 정의한다.
- `chat/service.py`의 반환 계약을 `reply` 외 메타데이터를 포함하는 구조로 바꿀지 검토한다.
- history 저장소와 운영용 recent activity read model을 분리할지 문서에 반영한다.
- archive 처리에 대해 별도 queue/outbox와 idempotency 키(`message_id` 등) 전략을 추가로 정의한다.

## 4. 메모리 업데이트
변경 없음
