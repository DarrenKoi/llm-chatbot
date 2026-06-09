# richnotification 인터랙티브 블록 — 제출 버튼 규약

> 최종 업데이트: 2026-05-05

이 문서는 `api/cube/intents.py` discriminated union 과
`api/cube/intent_renderer.py` 렌더링 계층에서 **사용자 입력을 다시 Flask 서버로
받아오는 경로**가 어떻게 동작하는지 정리합니다. LangGraph 워크플로가 사용자에게
선택지/입력란/날짜 선택을 보내고 다음 단계로 이어가는 흐름을 만들 때 반드시 이
규약을 맞춰야 합니다.

## 1. 왜 이 글을 읽어야 하나

Cube richnotification 은 **버튼 셀(`type: "button"`)을 사용자가 눌렀을 때만**
`callbackaddress` 로 결과를 POST 합니다. radio/checkbox/inputtext/textarea/
select/datepicker/datetimepicker 셀은 단말에서 값을 staged 상태로만 보관하며,
버튼이 같은 content 항목 안에 없으면 staged 값은 서버로 회신될 경로가 없습니다.

즉, **`choice` / `input` / `date` 같은 입력 블록을 emit 하는 응답에는 반드시
`button` 블록이 한 개 이상 같이 들어가야** 워크플로가 다음 턴으로 이어집니다.
이 규칙은 LLM 응답 경로(`api/llm/prompt/system.py` 시스템 프롬프트로 학습됨),
워크플로 코드 경로(`WorkflowReply.intents` 직접 채우기), 두 곳 모두에 동일하게
적용됩니다.

## 2. ButtonIntent 사용법

`api/cube/intents.py` 의 `ButtonIntent` 가 LLM/워크플로 양쪽이 채울 수 있는
스키마입니다. 최소 형태:

```json
{"kind": "button", "text": "보내기", "processid": "SendButton"}
```

전체 필드:

| 필드          | 기본값         | 비고 |
| ----------- | ----------- | --- |
| `text`      | (필수)        | 버튼 라벨. 워크플로 단계와 어울리는 문구로 정합니다. 예: "예약", "다음", "확정" |
| `processid` | `SendButton` | callback 결과 dispatch 시 매칭되는 process id. 단계별로 구분이 필요하면 다른 값 사용 |
| `value`     | `""`         | 클릭 시 함께 전송되는 식별자. 동일 화면에 버튼이 둘 이상이거나 의미가 다를 때 활용 |
| `confirmmsg`| `""`         | 클릭 직전 사용자에게 보여줄 확인 메시지. 비파괴 동작은 비워둡니다. |
| `bgcolor` / `textcolor` | `""` | hex 색상. 강조가 필요할 때만 지정합니다. |

### 사용 예 — LangGraph 워크플로 코드에서 직접 구성

```python
from api.cube.intents import ButtonIntent, ChoiceIntent, ChoiceOption, ReplyIntent

reply = ReplyIntent(
    blocks=[
        ChoiceIntent(
            question="회의실 선택",
            options=[
                ChoiceOption(label="A동 301", value="a301"),
                ChoiceOption(label="A동 401", value="a401"),
            ],
            processid="SelectRoom",
        ),
        ButtonIntent(text="예약", processid="ReserveBtn", value="reserve"),
    ],
    needs_callback=True,
)
```

### 사용 예 — LLM 응답(JSON)

```json
{
  "blocks": [
    {"kind": "text", "text": "어떤 형식으로 받으시겠어요?"},
    {"kind": "choice", "question": "형식",
     "options": [{"label": "PDF", "value": "pdf"}, {"label": "엑셀", "value": "xlsx"}],
     "processid": "SelectFormat"},
    {"kind": "button", "text": "보내기", "processid": "SendButton"}
  ],
  "needs_callback": true
}
```

## 3. 자동 보강(safety net)

LLM 또는 워크플로 코드가 버튼을 빠뜨려도 dead-end 응답이 나가지 않도록
`api/cube/intent_renderer.py` 의 `intents_to_content_item()` 이 다음 규칙으로
기본 제출 버튼을 자동 보강합니다.

- 입력형 intent(`choice` / `input` / `date`) 가 하나라도 있으면서
- `ButtonIntent` 가 한 개도 없으면
- → 마지막에 `ButtonIntent(text="보내기", processid="SendButton")` 가 자동 추가

자동 보강이 끼어들면 라벨/색상이 일반 기본값으로 노출되므로 가능하면 워크플로/
LLM 측에서 **명시적으로** ButtonIntent 를 함께 emit 하는 편이 좋습니다.

> `RawBlockIntent` 는 작성자가 row 를 수동으로 채우는 escape hatch 이므로 자동
> 보강 대상이 **아닙니다**. raw 블록만 있을 때 버튼이 필요하면 `ButtonIntent`
> 를 함께 넣거나 raw rows 에 직접 button cell 을 포함해야 합니다.

판정 함수는 `api.cube.intents.is_interactive_intent` 한 곳에 모여 있습니다.
새 입력형 intent 타입을 추가할 때는 같은 모듈의
`_INTERACTIVE_INTENT_TYPES` 튜플만 갱신하면 자동 보강 로직과 시스템 프롬프트가
동시에 반영됩니다.

## 4. processid 명명 규약

callback 결과는 `requestid` 매칭으로 dispatch 됩니다. 권장 규약:

- 입력 블록: 의미를 드러내는 명사형 — `SelectRoom`, `SelectFormat`, `InputCount`,
  `SelectDateTime`
- 제출 버튼:
  - 단일 화면이고 의미가 한 가지면 `SendButton`(기본값) 그대로 사용
  - 같은 화면에 의미가 다른 버튼이 둘 이상이면 `AgreeButton` / `RejectButton`
    처럼 동작별로 구분
  - 워크플로 단계를 더 나누고 싶으면 `value` 필드를 함께 사용

`requestid` 에 자동으로 합쳐지는 system id (`cubeuniquename`, `cubechannelid`,
`cubeaccountid`, `cubelanguagetype`, `cubemessageid`) 와 충돌하지 않도록
주의하십시오.

## 5. 팀원이 바뀐 동작에 맞춰 확인할 것

기존 LangGraph 서브그래프에서 `interrupt({"reply": ...})` 로 사용자에게
선택/입력을 요청하던 코드가 있다면 다음을 점검합니다.

1. interrupt payload 가 `ReplyIntent` 형태로 변환될 때 `ButtonIntent` 가
   같이 들어가는지(또는 들어가지 않더라도 `intents_to_content_item` 자동 보강이
   적용되는 경로인지) 확인합니다.
2. `processid` 가 워크플로 resume 노드에서 기대하는 값과 일치하는지 확인합니다.
   기본 자동 보강은 `SendButton` 으로 들어가므로 워크플로가 다른 id 를
   기대하면 명시적으로 emit 해야 합니다.
3. `value` 를 워크플로 분기 키로 쓰고 있다면 이전 코드가 비어 있던 자리에 새
   값을 넣어야 합니다.

새 워크플로를 만들 때는 `devtools/cube_message/samples.py` 의 `mixed_form`
샘플(예약 폼 + SendButton) 을 그대로 참고해 dev runner 에서 round-trip 을
검증하는 것을 추천합니다.

## 6. 관련 파일

- `api/cube/intents.py` — `BlockIntent` discriminated union, `ButtonIntent`,
  `is_interactive_intent`
- `api/cube/intent_renderer.py` — `intent_to_block`, `ensure_submit_button`,
  `intents_to_content_item`
- `api/cube/rich_blocks.py` — 저수준 cell/block 빌더(`make_button_cell`,
  `add_button`, `add_container`)
- `api/llm/prompt/system.py` — LLM 시스템 프롬프트 (button 스키마와 페어링 규칙)
- `tests/test_intents.py`, `tests/test_intent_renderer.py` — 회귀 테스트
- `devtools/cube_message/samples.py` — 실제 Cube 단말에 쏘는 디버그 페이로드
