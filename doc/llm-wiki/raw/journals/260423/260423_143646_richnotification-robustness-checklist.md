# Richnotification 견고성 체크리스트

Phase 1a(블록 팩토리 + intents + translator)는 완료되었고 55개 테스트가 통과하지만,
전송 파이프라인이 아직 새 모듈들을 사용하지 않는다. Phase 2(콜백 수신)로 넘어가기 전에
반드시 점검·보강해야 할 항목을 우선순위 순으로 정리한다.

---

## 현재 상태

### 완료된 부분
- `api/cube/rich_blocks.py` — label / button / choice / input / textarea / select / date /
  datetime / image / hypertext / table 블록 팩토리 + `compose_content_item` / `build_envelope`
- `api/cube/intents.py` — Pydantic discriminated union `BlockIntent` + `ReplyIntent`
- `api/cube/intent_renderer.py` — `intent_to_block` / `intents_to_content_item`
- 테스트: `test_rich_blocks.py`, `test_intents.py`, `test_intent_renderer.py` 전부 통과

### 문제의 핵심
- 새로 만든 3개 모듈은 **실제 전송 경로에서 아직 한 번도 호출되지 않는다** (죽은 코드).
- `payload.py:99`는 `{"text": reply_message}` 라는 **규격에 맞지 않는** content를 만든다.
- `service.py:326`은 chunker가 rich로 분류해도 원본 텍스트 문자열을 그대로 넘긴다.
- 즉, `CUBE_RICH_ROUTING_ENABLED=true`로 켜는 순간 Cube는 잘못된 페이로드를 받는다.

---

## 우선순위별 점검 항목

### 1. 전송 파이프라인 재배선 (최우선, 현재 죽은 코드)

- [ ] `api/cube/payload.py:87` `build_richnotification_payload`를
      `reply_message: str` 단일 인자에서 `str | list[Block]` (또는 intents)로 확장
      → 전략 문서 §4.2 참조
- [ ] `api/cube/client.py:63` `send_richnotification`이 블록/의도를 받도록 시그니처 변경
- [ ] `api/cube/service.py:326` rich 분기에서 `item.content` (코드/표 원본 텍스트)를
      `rich_blocks.table_block` / `text_block`으로 변환한 뒤 전송
- [ ] 위 3개 수정 전까지 `CUBE_RICH_ROUTING_ENABLED`는 OFF 유지 (현재 기본값 OFF 확인됨)

### 2. 콜백 수신기 (Phase 2 전제 조건)

- [ ] `api/cube/router.py` (현재 19줄)에 `callbackaddress` POST 수신 라우트 추가
- [ ] **형식 불명 대응**: 체크리스트 6번 — Cube의 POST body 구조가 아직 불명이므로
      Content-Type / 키 이름 / radio·checkbox 인코딩을 실측 후에야 파서 작성 가능
- [ ] `config.py`에 `CALLBACK_BASE_URL` 류 추가. 로컬 IP 금지 (DMZ 도달 가능해야 함)
      → 전략 문서 §5

### 3. 체크리스트 미완 항목 (사무실에서 실측 필요)

`richnotification_test_checklist.md`의 블랭크 항목들. 코드로는 검증 불가.

- [ ] 1번 — control type별 `active: false` 동작 (숨김/비활성화/회색처리)
- [ ] 5번 — `content[]` 복수 항목 렌더 방식 (탭/스크롤/페이지, 콜백 독립성)
- [ ] 6번 — 콜백 POST body 형식 (**Phase 2 블로커**)
- [ ] 7번 — `result` 필드 왕복 동작
- [ ] 8번 — `session.sessionid` / `sequence` 의미 (같은 id 재사용 시 덮어쓰기?)
      → 스트리밍·점진적 UX 설계에 영향
- [ ] 9번 — `channelid` 전송 대상 (uniquename과 병행 시)
- [ ] 10번 — `border`가 1/0 / "true" / true 중 무엇을 허용하는지

### 4. 스키마 불변식 (코드에서 강제해야 함)

- [ ] `_lang5`는 5개 미만이면 빈 문자열로 패딩하지만 6개 이상이면 **조용히 잘라버린다**.
      LLM 실수 잡으려면 초과 시 예외로 바꾸는 게 안전
- [ ] `mandatory[].processid`는 반드시 `requestid[]` 안에 존재해야 함 (rule.txt:338).
      `compose_content_item`에서 교차 검증 추가
- [ ] content item 내 `processid` 유일성 체크 (radio 그룹 예외). 현재 전무
- [ ] `image_block`의 `location` / `inner` 기본값이 `True` (DMZ 내부 전용).
      외부 URL에서는 반드시 깨짐 → 기본값 대신 호출자가 명시하도록 변경 고려

### 5. 워크플로 ↔ LLM 경계

- [ ] 현재 어떤 워크플로도 `ReplyIntent`를 반환하지 않음. 하이브리드 설계가 이론상에만 존재
- [ ] 결정 필요: 워크플로가 `ReplyIntent`를 반환하고 `service.py`가 변환할 것인가,
      워크플로가 직접 translator를 호출해 content item을 반환할 것인가
      → 전략 문서 §3은 전자를 전제
- [ ] 첫 도입 대상 워크플로 (start_chat or translator) 후보 선정 + `with_structured_output` 적용

### 6. 관측성

- [ ] `client.py:17`의 로그는 start/completed만 있음. 콜백이 돌아오기 시작하면
      `session.sessionid` + `requestid[]`를 송신 시 로그에 남겨 매칭 가능하게 만들 것
- [ ] "rich로 승격했다가 검증 실패로 multi로 폴백" 경로의 로그 이벤트 추가

### 7. 환경 설정 위생

- [ ] `CUBE_BOT_USERNAMES`가 정확히 5개인지 확인. `_lang5`가 padding해주긴 하지만
      Cube의 언어 인덱스 순서(한/영/일/중/기타)와 일치해야 함
- [ ] `CUBE_RICH_ROUTING_ENABLED`는 1번 완료 전까지 OFF 유지

---

## 권장 진행 순서

1. **먼저 1번 재배선**: 현재 Phase 1이 "코드는 있지만 죽어있는" 상태. 이걸 먼저 살림
   - `chunker.py`의 rich 분기(`code`/`table`)를 `rich_blocks.table_block` / `text_block` 경유로 연결
   - 이 시점에 단위 테스트가 실제로 Cube 규격 JSON을 생성하는지 확인 가능
2. **그다음 2번 콜백 수신기 스켈레톤**: 파서는 미완이어도 엔드포인트는 먼저 띄워야
   사무실에서 6번 테스트 가능
3. **4번 불변식**은 1번과 함께 추가. 저렴하고 LLM 실수 방어에 큰 효과
4. **3번 실측**은 사무실 환경 의존 — 집에서는 스텁으로 대체
5. **5번 워크플로 연결**은 위 전제가 다 서고 나서

---

## 참고

- 전략 문서: `doc/richnotification_전송_전략.md`
- 규격 원문: `richnotification_rule.txt`
- 샘플: `richnotification_samples.md`
- 체크리스트 원본: `richnotification_test_checklist.md`
