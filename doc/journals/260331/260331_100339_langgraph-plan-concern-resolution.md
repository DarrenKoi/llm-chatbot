## 1. 진행 사항

- `doc/랭그래프_api_구조_계획.md` 계획 문서를 `doc/journals/260331/260331_094816-langgraph-plan-review-concerns.md`에 기록된 4가지 설계 우려와 대조하여 검토했다.
- 현재 코드베이스(`api/cube/service.py`, `api/conversation_service.py`, `api/llm/service.py`, `api/cube/models.py` 등)의 실제 구현을 분석하여 우려 사항의 영향을 확인했다.
- 각 우려에 대한 권장안을 도출하고, 사용자 확인 후 계획 문서에 반영했다.
- Cube 응답 포맷(multimessage vs richnotification) 관련 새로운 설계 요소를 추가했다.

### 검토한 4가지 우려와 결론

1. **Checkpointer thread_id 전략** → `user_id` 단독 사용. 모델 선호는 `user_id:channel_id` 키로 별도 저장.
2. **chat/service.py 반환 계약** → `ChatResult` 구조체 도입 (`reply`, `model_used`, `tool_calls`, `thread_id`).
3. **conversation_service.py 제거 시 orphan 책임** → `get_recent()`는 별도 read model로 분리, MongoDB fallback은 제거하고 환경별 명시적 checkpointer 선택.
4. **비동기 아카이빙 멱등성** → `message_id`를 OpenSearch doc ID로 사용 (upsert), Redis `reply_sent` 플래그로 Cube 중복 전송 방지.

### Cube 응답 포맷 추가 사항

- **multimessage**: plain text, 복사 가능, 현재 사용 중
- **richnotification**: 이미지 기반, 복사 불가, 테이블/버튼/메뉴 지원, 미구현
- 초기에는 multimessage만 사용하고, 이후 콘텐츠 유형에 따라 두 포맷을 조합
- `cube/service.py`가 `ChatResult` 기반으로 포맷 라우팅 담당, `chat/`은 Cube 포맷을 모름

## 2. 수정 내용

- **수정 파일**: `doc/랭그래프_api_구조_계획.md`
- 코드 변경 없음 (계획 문서만 업데이트)

### 구체적 변경 내역

| 섹션 | 변경 내용 |
|---|---|
| §2.4 | 제목 변경 ("응답 포맷 라우팅을 담당한다" 추가), multimessage vs richnotification 비교 테이블 및 전략 추가 |
| §2.5 (신규) | `ChatResult` 구조체 반환 원칙 추가 |
| §2.6 (구 2.5) | 번호 재배정 (내용 변경 없음) |
| §2.7 (구 2.6) | thread_id 전략, 개발/운영 환경 분리, 운영 대시보드용 read model 서브섹션 추가 |
| §4.1 | cube/ 책임에 응답 포맷 라우팅 추가, `ChatResult` 기반으로 설명 갱신 |
| §4.2 | 반환값을 `ChatResult`로 갱신 |
| §4.7 | 아카이빙 타이밍 흐름도를 `ChatResult` 기반으로 갱신, 멱등성 전략 서브섹션 추가 |
| §8 | 마이그레이션 변경 후 흐름을 `ChatResult` 및 포맷 라우팅 반영하여 갱신 |
| §10.1 | `run_chat_workflow` 시그니처를 `ChatResult` 반환으로 변경, 구조체 정의 추가 |
| §10.2 | `thread_id = user_id` 명시, §2.7 참조 추가 |

## 3. 다음 단계

- 계획 문서가 충분히 구체화되었으므로, 초기 구현 범위(§9.1)에 따라 실제 코드 작업을 시작할 수 있다.
- 우선순위:
  1. `api/llm/registry.py` — `ChatOpenAI` 기반 모델 레지스트리 구현
  2. `api/chat/models.py` — `ChatResult` 구조체 정의
  3. `api/chat/service.py` — `run_chat_workflow()` 진입점 뼈대
  4. `api/workflows/chat/` — LangGraph graph, state, nodes 초기 구현
  5. `api/cube/service.py` — `ChatResult` 기반으로 기존 `process_incoming_message` 리팩터링
- richnotification 포맷 스펙은 실제 구현 시 별도로 정의가 필요하다.

## 4. 메모리 업데이트

변경 없음
