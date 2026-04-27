# multimessage / richnotification 스마트 스위칭 구현 계획

> 짝꿍 문서: `doc/richnotification_전송_전략.md` (전략·철학)
> 이 문서: 그 전략을 실제 코드에서 어떻게 켜고/관리할지의 **구현 계획**

## 1. 배경

`doc/richnotification_전송_전략.md`에 정리된 하이브리드 설계의 요점:

- **Python = 스키마 권한자.** 블록 팩토리(`api/cube/rich_blocks.py`)가 5개 언어
  배열, `processid` 명명, header/process 봉투 같은 비자명한 규칙을 전담한다.
- **LLM = 의도(intent) 생성자.** richnotification 원본 JSON은 절대 만지지 않고,
  Pydantic `ReplyIntent` 스키마(`api/cube/intents.py`)만 채운다.
- **Translator = intent → Block 변환.** `api/cube/intent_renderer.py`가
  intent를 `rich_blocks.Block`으로 매핑한다.

본 문서는 위 전략을 따라 LLM 응답 형태에 따라 **multimessage / richnotification을
자동으로 골라 보내는** 라우팅을 어떻게 구현·검증·확장할지 정리한다.

## 2. 현재 상태 요약 (2026-04-27 기준)

| 컴포넌트 | 상태 | 위치 |
| --- | --- | --- |
| Intent 스키마 | ✅ 완료 | `api/cube/intents.py` (Pydantic v2) |
| Intent → Block 렌더러 | ✅ 완료 | `api/cube/intent_renderer.py` |
| Escape hatch (`RawBlockIntent`) | ✅ 완료 | `api/cube/intents.py` (§12) |
| 블록 팩토리 (production) | ✅ 완료 | `api/cube/rich_blocks.py` |
| 블록 팩토리 probe (devtools) | ✅ 완료 | `devtools/cube_message/samples.py` |
| LLM intent 생성 | ✅ 완료 | `api/llm/service.py::generate_reply_intent` |
| WorkflowReply에 intent 필드 | ✅ 완료 | `api/workflows/models.py` |
| 그래프 상태에 intent 필드 | ✅ 완료 | `api/workflows/lg_state.py::ChatState` |
| start_chat 그래프 노드 연결 | ✅ 완료 | `api/workflows/start_chat/lg_graph.py` |
| Cube 서비스 라우팅 분기 | ✅ 완료 | `api/cube/service.py:372-396` |
| 시스템 프롬프트 가이드 | ✅ 완료 | `api/llm/prompt/system.py::DEFAULT_SYSTEM_PROMPT` |
| translator 그래프 마이그레이션 | ⏳ 미적용 | `api/workflows/translator/` |
| 사무실 실측 (block probe sweep) | ⏳ 진행 예정 | `devtools/cube_message/examples.py` |
| `richnotification_rule.txt` 갱신 | ⏳ 사무실 결과 반영 후 | 루트 |

`✅`로 표시된 항목은 commit `8c561c3` 시점에 main에 올라가 있다.

## 3. 스위칭 결정 트리

요청이 들어오면 다음 순서로 전송 방식을 정한다.

```
LLM 응답 (ReplyIntent)
  │
  ├─ intents가 None 또는 빈 리스트?
  │     → 평문 fallback. plan_delivery()가 마크다운 표/코드 펜스를 감지해
  │       multimessage 또는 richnotification(text-only)로 보낸다.
  │
  ├─ intents에 비-Text intent(choice/input/date/image/table)가 한 개라도 있는가?
  │     → richnotification 블록 경로:
  │         intents_to_blocks(intents) → send_richnotification_blocks(*blocks)
  │       send_richnotification_blocks가 requestid 유무를 보고 callback URL을
  │       자동 첨부한다(콜백 자격증명도 봇 자격으로 분리 적용).
  │
  └─ intents가 모두 TextIntent 뿐?
        → 평문 fallback과 동일. text 본문을 합쳐 plan_delivery()로 흘린다.
          (구조 블록을 굳이 쓸 이유가 없다는 LLM의 판단을 존중)
```

이 분기 로직은 `api/cube/service.py:372-396` 한 곳에 있다.

```python
intents = workflow_result.intents
has_structured_intent = bool(intents) and any(
    not isinstance(i, TextIntent) for i in intents
)

if has_structured_intent:
    blocks = intents_to_blocks(intents)
    send_richnotification_blocks(*blocks, user_id=..., channel_id=...)
else:
    for item in plan_delivery(llm_reply):
        if item.method == "rich":
            _send_rich_delivery_item(...)
        else:
            send_multimessage(...)
```

## 4. 데이터 흐름

```
Cube webhook
  → service.process_incoming_message
    → lg_orchestrator.handle_message
      → start_chat 그래프
        → generate_reply_node
          → llm.service.generate_reply_intent ── ReplyIntent
                ├─ messages: [AIMessage(text_fallback)]   # legacy 경로용
                └─ reply_intents: list[BlockIntent]|None  # 구조 경로용
      ← orchestrator가 state.reply_intents를 WorkflowReply.intents로 노출
    ← service가 intents를 보고 richnotification / multimessage 분기
```

핵심 포인트:

- **이중 표현**: 그래프 노드는 항상 `messages`(평문) **와** `reply_intents`(구조)를
  같이 적재한다. 라우터가 어느 쪽이든 안전하게 쓸 수 있게 하기 위함.
- **structural fallback이 항상 보장된다.** `generate_reply_intent`는 어떤 경우에도
  최소 1개의 `TextIntent`를 가진 `ReplyIntent`를 반환한다 (§5 참조).

## 5. `generate_reply_intent`의 3단 폴백

`api/llm/service.py:49-96`. 약한 LLM(Kimi-K2.5 / Qwen3 / GPT-OSS)이 도구 호출이나
구조 출력을 반드시 지원한다고 가정할 수 없으므로 단계적으로 약화한다.

| 단계 | 시도 | 성공 조건 | 실패 시 |
| --- | --- | --- | --- |
| 1 | `llm.with_structured_output(ReplyIntent).invoke(messages)` | LangChain이 도구 호출로 Pydantic 스키마 강제 | 경고 로그 후 단계 2 |
| 2 | 평문 응답에서 ```json``` 펜스 추출 → `ReplyIntent.model_validate_json` | 펜스 안의 JSON이 스키마와 일치 | 단계 3 |
| 3 | 평문 전체를 `TextIntent(text=raw)`로 감싸기 | 항상 성공 | (없음) |

**의도된 부산물**: 사용자에게 응답이 가지 않는 경로가 없다. 스키마가 깨져도
"적어도 평문 답변"은 나간다. 사일런트 실패 대신 항상 *무언가*를 보낸다.

## 6. 시스템 프롬프트 가이드

`api/llm/prompt/system.py::DEFAULT_SYSTEM_PROMPT`에 한국어 escalation 규칙과
짧은 예시 두 개를 넣었다. 길이를 짧게 유지해 약한 LLM이 패턴을 그대로
모방하게 한다.

핵심 규칙(요약):

```
[응답 형식 가이드]
기본은 평문 텍스트(blocks=[{"kind":"text", ...}])이다.
다음 중 하나일 때만 구조 블록으로 승격한다:
1) 정확한 레이아웃이 필요할 때 — 표(`table`), 이미지(`image`)
2) 사용자 입력이 필요할 때 — 선택(`choice`), 입력(`input`), 날짜(`date`)
3) 분할 시 의미가 깨질 때 — 한 메시지에 묶어 보내야 할 때
```

이 규칙은 전략 문서 §2의 "확성기 vs 양식지" 판단 원칙을 LLM 친화적으로 옮긴 것.

## 7. 사무실 실측 단계 (probe sweep)

LLM에게 "이런 블록 쓸 수 있다"고 가르치기 전에, **각 블록이 실제 Cube에서
어떻게 보이는지** 사람이 먼저 본다.

`devtools/cube_message/samples.py`에 등록된 probe 16종 중 production 블록을
직접 호출하는 10종이 이 단계의 대상.

| Probe 이름 | 확인 대상 |
| --- | --- |
| `buttons_basic` | bgcolor / textcolor / confirmmsg / clickurl |
| `radio_choice` | 라디오 그룹 default 선택, mandatory alertmsg |
| `checkbox_choice` | 다중 선택 callback value 배열 형태 |
| `select_dropdown` | 드롭다운 vs 라디오 시각 차이 |
| `input_field` | placeholder, min/maxlength, validmsg 트리거 시점 |
| `textarea_field` | height, 줄바꿈, validmsg |
| `datepicker_basic` | YYYY/MM/DD default, picker UI |
| `datetimepicker_basic` | YYYY/MM/DD HH:MM, 분 단위 UI |
| `image_basic` | displaytype, location/inner DMZ 동작 |
| `mixed_form` | 여러 processid 공존 시 callback payload |

실행: 사무실에서 본인 Cube ID로 `examples.py`의 `CONFIG`를 채우고
`python -m devtools.cube_message.examples` 실행. 발견 사항을
`richnotification_rule.txt`에 누적 반영한다.

## 8. 검증

### 자동 (집/사무실 모두)

```bash
ruff check . && ruff format --check .
pytest tests/ -v
```

핵심 테스트:

- `tests/test_llm_service.py` — `generate_reply_intent`의 3단 폴백 각각 (4 케이스)
- `tests/test_cube_service.py` — 구조 intent → richnotification, 텍스트만
  → multimessage 분기 (2 케이스)
- `tests/test_devtools_cube_message.py` — probe 10종 페이로드 형태 (parametrized)
- 기존 `tests/test_intents.py` / `tests/test_intent_renderer.py` — 회귀

`8c561c3` 시점 기준 331개 테스트 통과.

### 수동 (사무실 한정)

1. probe sweep으로 블록별 렌더링 확인 (§7).
2. start_chat 입력으로 다음을 시도:
   - **평문 케이스**: "안녕하세요" → multimessage 한 건.
   - **표 케이스**: "최근 일주일 처리 통계 표로" → 마크다운 표 → chunker 경로 →
     richnotification 표.
   - **선택 케이스**: "PDF로 받을까요 엑셀로 받을까요?" → ChoiceIntent 생성 →
     richnotification 드롭다운/라디오 렌더링.
3. 각각의 결과를 Cube 화면에서 확인하고, `richnotification_rule.txt`에 발견된
   한계/팁을 추가한다.

## 9. 남은 작업 (Stage 4 이후)

전략 문서 §4.4의 4단계 롤아웃 중 다음이 미완:

- **translator 워크플로 마이그레이션** — `api/workflows/translator/lg_graph.py`도
  `generate_reply_intent`로 교체. 번역 결과를 코드 블록으로 보여줄 때 그대로
  text intent에 머무르게 두면 chunker가 알아서 처리한다(추가 작업 거의 없음).
  단, 언어 선택을 ChoiceIntent로 묻는 패턴은 LLM 재학습 필요.
- **새 BlockIntent 종류 추가** — list / container / button-only-without-choice.
  먼저 `intents.py`에 모델 추가 → `intent_renderer.py`에 매핑 → 시스템 프롬프트에
  사용 시점 명시 → probe 추가.
- **신뢰도 측정** — 각 LLM(Kimi-K2.5/Qwen3/GPT-OSS)에서 `with_structured_output`
  성공률을 실측. 폴백 단계별 빈도를 메트릭으로 노출 (단계 1 성공 / 단계 2 폴백 /
  단계 3 폴백)하면 어느 모델이 어디까지 견디는지 보인다. 위치: `generate_reply_intent`
  내부에 `log_activity` 호출 추가.
- **per-graph 시스템 프롬프트 오버라이드** — `start_chat`과 `translator`가 다른
  설명을 필요로 할 가능성. 지금은 `DEFAULT_SYSTEM_PROMPT` 한 곳만 손댔음.
- **콜백 처리** — `processid`로 받은 사용자 응답을 다음 워크플로 단계와 연결하는
  로직. 현재는 콜백을 받을 수는 있지만 그래프 재진입 흐름이 미정.

## 10. Python 호환성 노트

사무실 환경은 **Python 3.11**.

이번 구현에서 사용한 기능 중 3.11 호환성 검토:

- `X | None` union 표기 (PEP 604) — 3.10+ 정식. ✅
- `list[BlockIntent]` 등 PEP 585 generic — 3.9+. ✅
- `from typing import Annotated, TypedDict, TYPE_CHECKING` — 3.11 정상. ✅
- LangChain `ChatOpenAI.with_structured_output(PydanticModel)` — 3.11이 주 타깃. ✅
- Pydantic v2 `model_validate_json` — 3.11 호환. ✅
- 3.12+ 신문법(`class Foo[T]:`, `type` statement, `@override` from typing) — **사용 안 함**. ✅

LangGraph가 `get_type_hints(schema, include_extras=True)`로 `ChatState`의 타입
힌트를 빌드 시점에 평가하므로, `lg_state.py`에서 `BlockIntent`를 `TYPE_CHECKING`
가드 없이 **무조건 임포트**해야 한다. 이미 그렇게 되어 있고 3.11/3.14 양쪽에서
같은 동작이다.

집(3.14)에서 보이는 `pydantic.v1 ... isn't compatible with Python 3.14` 경고는
3.14 전용. 사무실(3.11)에서는 뜨지 않는다. 조치 불필요.

## 11. 신규 BlockIntent 추가 — 4단계 레시피

팀원이 새로운 블록 종류(예: 진행률 바, 슬라이더 등)를 LLM에 가르치고 싶을 때
이 절차를 그대로 따른다. 라우팅 / 전송 / 워크플로 코드는 건드릴 필요 없다.

1. **`api/cube/intents.py`** — Pydantic 모델 추가, `BlockIntent` 유니언에 등록.
   ```python
   class ProgressIntent(BaseModel):
       kind: Literal["progress"] = "progress"
       label: str
       percent: int   # 0~100

   BlockIntent = Annotated[
       TextIntent | ... | ProgressIntent,   # 추가
       Field(discriminator="kind"),
   ]
   ```

2. **`api/cube/intent_renderer.py`** — 한 줄 분기를 추가. 새 helper가
   `rich_blocks.py`에 없으면 거기에도 같이 추가한다(스키마 권한자 = Python).
   ```python
   if isinstance(intent, ProgressIntent):
       return rich_blocks.add_progress_bar(intent.label, intent.percent)
   ```

3. **`api/llm/prompt/system.py`** — 한 줄 규칙 + 짧은 예시 하나. 길게 쓰지 않는다.
   ```
   - progress: 작업 진행률을 보여줄 때 사용 (label + percent 0~100)
   예) blocks=[{"kind":"progress","label":"업로드 중","percent":42}]
   ```

4. **`devtools/cube_message/samples.py`** — probe 함수 + `SAMPLES` / `_FACTORIES`
   등록. 사무실에서 실측해서 어떻게 렌더링되는지 확인 후 §12와
   `richnotification_rule.txt`에 기록한다.

테스트는 기존 패턴을 그대로 복붙: `tests/test_intents.py`의 discriminator 케이스
1개, `tests/test_intent_renderer.py`의 `intent_to_block` 케이스 1개. 두 곳 모두
한 줄짜리 assertion이면 충분하다.

레시피의 핵심: **워크플로 코드, 라우팅 코드, LLM 클라이언트는 건드리지 않는다.**
새 종류는 항상 (intent → renderer → prompt → probe) 4파일 변경으로 끝난다.
이 경계가 흐려지면 다음 사람이 무엇을 어디에 추가해야 할지 모르게 된다.

## 12. Escape hatch: `RawBlockIntent`

추상 BlockIntent로 표현이 어려운 케이스(스키마에 없는 컨트롤, 복잡한 그리드,
아직 §11 레시피로 추가하지 않은 패턴)를 위해 `RawBlockIntent`를 제공한다.

```python
from api.cube.intents import RawBlockIntent

# 워크플로 코드에서 직접 만들어 WorkflowReply.intents에 넣는다.
custom_block = RawBlockIntent(
    rows=[
        {
            "bgcolor": "",
            "border": False,
            "align": "left",
            "width": "100%",
            "column": [
                # rich_blocks.py의 add_*가 만들어내는 column dict 그대로
            ],
        }
    ],
    requestid=["MyCustomProcess"],
    bodystyle="grid",   # 또는 "none"
)
```

### 언제 쓰는가

- ✅ 일회성 / 워크플로 한정 패턴이라 추상 intent로 만들 가치가 없을 때
- ✅ 스파이크/실험 단계 — 작동을 확인한 뒤 §11 레시피로 정식 intent화할 예정일 때
- ❌ **여러 워크플로가 같은 모양을 필요로 할 때** — 그건 §11 레시피로
   `BlockIntent`를 추가하는 게 맞다
- ❌ LLM이 직접 채우게 하지 말 것. `RawBlockIntent`는 시스템 프롬프트의 LLM
   가이드에 노출하지 않는다. 워크플로 코드가 수동으로 넣는 용도다.

### 동작

`intent_renderer.intent_to_block()`이 `RawBlockIntent`를 받으면 `rich_blocks.Block(
rows=..., mandatory=..., requestid=..., bodystyle=...)`를 그대로 만들어 반환한다.
이후 `add_container` 단계에서 시스템 ID가 자동 추가되고, `requestid`가 비어 있지
않으면 라우터가 콜백 URL을 자동 첨부한다. 다른 정식 intent와 똑같이 흐른다.

### 안티패턴

- 워크플로 안에서 `from api.cube.client import send_richnotification_blocks`를
  직접 호출 → ❌ 채널 의존성이 워크플로에 박힌다. 항상 `WorkflowReply.intents`로
  반환하라.
- `RawBlockIntent`로 덮어쓰면서 `rich_blocks.add_*`를 안 쓰고 row dict를
  처음부터 손으로 짜기 → ⚠️ 가능하지만 5개 언어 배열, `processid`, `mandatory`
  교차 참조 같은 규칙을 직접 지켜야 한다. `rich_blocks.add_button(...).rows`
  같은 식으로 정식 헬퍼의 결과를 빼서 쓰는 게 안전하다.

## 13. 참고

- 전략: `doc/richnotification_전송_전략.md`
- 규격 원문: `richnotification_rule.txt`
- 검증된 JSON 예시: `richnotification_samples.md`
- 검증 체크리스트: `richnotification_test_checklist.md`
- Probe 스크립트: `devtools/cube_message/samples.py`, `devtools/cube_message/examples.py`
- 핵심 코드 진입점:
  - `api/llm/service.py::generate_reply_intent` — 의도 생성·폴백
  - `api/cube/intents.py` — Pydantic 스키마
  - `api/cube/intent_renderer.py` — 의도 → Block 변환
  - `api/cube/rich_blocks.py` — Block / Cell 팩토리
  - `api/cube/service.py:372` — multimessage / richnotification 분기점
  - `api/llm/prompt/system.py` — escalation 규칙
