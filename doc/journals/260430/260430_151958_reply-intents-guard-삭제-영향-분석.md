# reply_intents 가드 삭제 시 발생 가능한 이슈 분석

## 1. 진행 사항

- 팀원이 제안한 변경 — `api/workflows/lg_orchestrator.py:227`의 `if not result_state.tasks else None` 가드 제거 — 의 실제 영향 범위를 분석.
- 현재 가드의 의미와 `reply_intents`가 LangGraph 체크포인터에 어떻게 영속되는지 코드 트레이싱.
  - `api/workflows/lg_orchestrator.py:206-232` (interrupt 분기 및 intents 추출)
  - `api/workflows/start_chat/lg_graph.py:142-161` (`generate_reply_node`에서 `reply_intents` 채우는 지점)
  - `api/workflows/lg_state.py:14-26` (`ChatState.reply_intents` 정의)
  - `api/workflows/translator/lg_graph.py:53-64` (`interrupt(...)` 호출 패턴)
  - `api/cube/service.py:476-497` (`intents` 유무에 따른 분기 — `_send_intent_reply` vs `_send_plain_text_reply`)
- 팀원이 진짜 원하는 것이 "되묻기 기능 구현"이라는 가정 하에, LangGraph의 `interrupt()` 패턴과 `start_chat` 그래프에 되묻기 노드를 추가하는 구체적 코드 예시 제공.

## 2. 수정 내용

- 코드 변경 없음 (분석/설계 세션).
- 검토 대상 라인: `api/workflows/lg_orchestrator.py:227`
  ```python
  intents = result_state.values.get("reply_intents") if not result_state.tasks else None
  ```

## 3. 가드 삭제 시 발생 가능한 이슈

### 핵심 메커니즘
- `result_state.tasks`는 그래프가 `interrupt(...)`로 멈춰 사용자 입력을 대기 중일 때만 채워진다 (정상 종료 시 빈 튜플).
- `reply_intents`는 LangGraph 체크포인터가 thread_id 단위로 **state에 영속 저장**한다. 한 번 채워두면 다음 턴까지 **자동으로 살아남는다**.
- interrupt 턴의 실제 응답 텍스트는 `interrupt_value["reply"]` (lg_orchestrator.py:209-210)에서 나오며, `reply_intents`와는 별개다.

### 시나리오별 영향

| 시나리오 | 현재 (가드 있음) | 가드 제거 시 |
|---------|-----------------|--------------|
| A. 워크플로 정상 종료 | start_chat이 만든 intents 전송 | 동일 (변화 없음) |
| B. interrupt 직전 턴에 `reply_intents`가 이미 존재 | intents=None → interrupt의 "되묻는 텍스트"가 평문으로 정상 전송 | **묵은 카드가 또 전송**, "되묻는 텍스트"는 사라짐 ❌ |
| C. interrupt 턴인데 `reply_intents`가 None | None → 평문으로 안전 전송 | 동일 (변화 없음) |

### 시나리오 B의 구체 예시
1. **1턴**: 사용자 "오늘 날씨 알려줘" → start_chat이 날씨 카드를 만들어 `reply_intents`에 저장 → 카드 전송 ✅. **메모장(state)에 카드가 그대로 남음**.
2. **2턴**: 사용자 "!translate" → translator가 "원문을 입력해주세요"라고 `interrupt(...)` 발동.
3. 가드가 없으면 `intents`에 1턴의 묵은 날씨 카드가 들어가고, `cube/service.py:480`의 `if intents:` 분기에서 **묵은 카드를 또 전송**하며 "원문을 입력해주세요" 텍스트는 영영 출력되지 않음.

### 결론
- 라인 227의 가드는 **이전 턴의 reply_intents가 다음 턴의 interrupt 화면에 stale-leak되는 것**을 막는 안전장치다.
- "되묻기로 대화를 이어간다"는 기능은 이미 translator의 `interrupt(...)` 메커니즘이 제공하고 있으며, 라인 227 수정과는 직교한다.
- 라인 227만 단순 삭제하면 multi-turn 대화 능력은 늘지 않고 시나리오 B의 stale-intent 누출 회귀만 발생한다.

## 4. 되묻기 기능을 진짜 구현하려면

팀원의 의도가 "interrupt 프롬프트도 카드 형태로 보여주고 싶다"라면 다음 중 하나가 필요하다:

1. **interrupt를 발동하는 노드가 그 턴의 `reply_intents`를 새로 채운다** — 예: translator의 `collect_*_node`가 `{"user_message": ..., "reply_intents": [TextIntent(text=pending_reply)]}` 반환.
2. **interrupt 진입 시점에 `reply_intents`를 명시적으로 클리어**한다 — 묵은 값 누출 방지.
3. **오케스트레이터 라인 209-210에서 `interrupt_value`의 `intents` 키도 함께 꺼낸다** — `interrupt({"reply": text, "intents": [...]})` 형태로 dict를 풍부하게 넘기고 매핑. (분석 결과 가장 작고 깔끔한 변경 지점)

start_chat에 "모호한 질문 되묻기" 노드를 새로 추가하는 패턴 예시 (대화 본문 참고):
- `ask_clarification_node`에서 `interrupt({"reply": question})` 호출
- `classify_node`에서 `needs_clarification` 플래그 세팅
- `_route_after_classify`에서 분기 추가
- `builder.add_node` / `builder.add_edge`로 그래프에 등록
- 오케스트레이터는 `current.tasks` 유무로 새 호출 vs resume을 자동 분기하므로 **수정 불필요**

## 5. 다음 단계

- **팀원에게 의도 확인 필요** — 다음 세 가지 중 어느 것인지 인터뷰:
  1. 단순히 "되묻는 화면이 카드로 안 나온다" → 위 옵션 3 (오케스트레이터 line 209-210에서 intents 추출) 적용
  2. start_chat이 모호한 질문에 되묻지 않는다 → `ask_clarification_node` 추가 (예시 코드는 본 대화 참조)
  3. 다른 워크플로(translator 외)에서도 multi-turn이 필요하다 → 해당 워크플로에 `interrupt()` 노드 추가
- 의도가 1번이면, `WorkflowReply.intents`에 interrupt-time intents를 매핑하는 분기를 추가하고 회귀 테스트 작성:
  - `tests/test_lg_orchestrator.py`에 시나리오 B (이전 턴 reply_intents가 살아있는 상태에서 interrupt 진입) 케이스 추가하여 stale-leak 회귀 방지.

## 6. 메모리 업데이트

변경 없음. (이번 세션은 분석/설계만 진행, 코드 변경 및 신규 컨벤션 도입 없음. 단, 향후 옵션 1~3 중 어느 방향으로 결정되면 `project_langgraph_migration.md` 또는 신규 `project_workflow_interrupt_pattern.md`에 결정 사항 기록 필요.)
