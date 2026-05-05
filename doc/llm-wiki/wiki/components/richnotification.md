---
tags: [component, cube, workflow]
level: intermediate
last_updated: 2026-05-05
status: stable
owner: llm-chatbot 팀
sources:
  - api/cube/intents.py
  - api/cube/intent_renderer.py
  - api/cube/rich_blocks.py
  - api/cube/service.py
  - api/cube/client.py
  - api/cube/payload.py
  - api/llm/service.py
  - api/llm/prompt/system.py
  - api/workflows/lg_orchestrator.py
  - api/workflows/start_chat/lg_graph.py
---

# richnotification 메시지 만들기 — 데이터 흐름과 워크플로 작성 가이드

> 한 줄 요약 — Cube의 richnotification 메시지가 워크플로 응답으로부터 어떻게 만들어지는지, 그리고 워크플로에서 블록을 안전하게 생성하려면 무엇을 신경 써야 하는지를 정리한 팀용 가이드.

이 문서는 다음 두 가지를 다룬다.

1. 워크플로 → 의도(intent) → Block → richnotification payload → Cube 호출까지의 **전체 데이터 흐름**.
2. 새 워크플로(또는 기존 워크플로 노드)에서 블록을 만들 때 **블록이 깨지지 않도록 신경 써야 할 점**.

---

## 1. 큰 그림 — 4계층 파이프라인

richnotification은 다음 4단계를 거친다. 위 계층일수록 추상적(intent), 아래로 갈수록 Cube 규격에 가까운 raw JSON이다.

```
[워크플로 노드]                         ← LangGraph 상태에 reply_intents 적재
        │  list[BlockIntent]
        ▼
[api/cube/intents.py]                   ← 의도(Discriminated union)
        │  Pydantic 모델 (LLM과 직접 호환)
        ▼
[api/cube/intent_renderer.py]           ← intent_to_block()
        │  rich_blocks.Block 리스트
        ▼
[api/cube/rich_blocks.py]               ← add_container() / build_richnotification()
        │  Cube richnotification payload (dict)
        ▼
[api/cube/client.py]                    ← httpx.post(CUBE_RICHNOTIFICATION_URL, ...)
```

핵심은 **워크플로 코드와 LLM은 raw JSON을 절대 직접 만들지 않는다**는 점이다. 두 계층 모두 `BlockIntent`를 채워 반환하고, 그 아래는 `intent_renderer` + `rich_blocks`가 책임진다. 이 경계를 지키는 한 Cube 스키마가 바뀌어도 워크플로 코드를 고칠 필요가 거의 없다.

---

## 2. 단계별 데이터 흐름

### 2.1 워크플로 노드가 의도를 만든다

LangGraph 노드는 자기 상태에 `reply_intents: list[BlockIntent] | None` 키를 채운다. 두 가지 경로가 있다.

**경로 A — LLM이 직접 의도를 채우는 경우**
대표 예시는 `start_chat`의 `generate_reply_node`다 (`api/workflows/start_chat/lg_graph.py:106`).

- `api.llm.service.generate_reply_intent()`를 호출 → LLM이 `ReplyIntent` (Pydantic) 형태로 응답
  - 1차: `with_structured_output(ReplyIntent, method="function_calling")`
  - 2차(폴백): 평문에서 JSON 추출 → `ReplyIntent.model_validate`
  - 3차(최후): 평문 전체를 `TextIntent` 한 개로 감싸 반환
- 구조 블록(`TextIntent`가 아닌 것)이 하나라도 있으면 `reply_intents`에 그 리스트를 그대로 저장한다.

**경로 B — 워크플로 코드가 직접 의도를 만드는 경우**
정형화된 폼(예: 결재 양식, 검색 결과 표 등) 같이 LLM에 맡길 필요가 없는 케이스다. 노드는 `BlockIntent` 객체(`ChoiceIntent`, `TableIntent`, ...)를 직접 생성해 `reply_intents`에 넣는다. 어떤 BlockIntent로도 표현되지 않는 케이스는 escape hatch인 `RawBlockIntent`를 사용한다.

### 2.2 오케스트레이터가 결과를 묶어 반환한다

`api/workflows/lg_orchestrator.py:227`에서 그래프 실행 후 상태에서 `reply_intents`를 꺼내, 평문 `reply`와 함께 `WorkflowReply(reply, workflow_id, intents)` (`api/workflows/models.py:26`)로 감싸 cube 서비스 계층에 넘긴다.

- `intents`가 `None`이면: 평문 `reply`만 chunker 경로(`_send_plain_text_reply`)로 전송된다.
- `intents`가 있으면: `_send_intent_reply` 경로로 라우팅된다.

### 2.3 cube 서비스 계층이 의도를 그룹핑해 전송한다

`api/cube/service.py`의 `_send_intent_reply`(353줄)는 `intents` 리스트를 순회하며 다음 규칙으로 묶어 보낸다.

- 연속된 `TextIntent`는 한 multimessage(평문)로 묶어 보낸다.
- `TextIntent`가 아닌 의도(구조 블록)는 함께 누적해 `send_richnotification_blocks(*blocks, ...)` 한 번으로 보낸다.
- 텍스트 → 구조 → 텍스트처럼 끼워들 때마다 그룹이 끊어져 별개 호출로 전송된다.
- 호출 사이에는 `CUBE_DELIVERY_DELAY_SECONDS`만큼 sleep이 들어간다(메시지 순서 보장 목적).

> **함의** — 워크플로에서 `[Text, Choice, Text, Image]` 4개를 보내면 Cube에는 4번 호출이 나간다. 같은 채팅 화면에 한 풍선으로 묶고 싶으면 한 그룹(예: 모두 구조 블록)으로 만들거나 add_container 단위로 합쳐야 한다.

### 2.4 intent_renderer가 Block으로 변환한다

`api/cube/intent_renderer.py:23` `intent_to_block()`이 의도 종류별로 `rich_blocks.add_*` 헬퍼를 호출해 `Block`을 만든다. `Block`은 `(rows, mandatory, requestid, bodystyle)`을 모은 dataclass다(`rich_blocks.py:72`).

대화 이력 저장에는 raw JSON이 아닌 `intents_to_history_text()` 결과(예: `"[선택지] 형식 (옵션: PDF, 엑셀)"`)가 들어간다. LLM이 다음 턴에 맥락을 이어갈 수 있도록 사람도 LLM도 읽을 수 있는 한국어 다이제스트로 변환한다.

### 2.5 rich_blocks가 컨테이너 + payload를 조립한다

`rich_blocks.add_container(*blocks, callback_address, session_id, ...)` 가 모든 Block의 `rows / mandatory / requestid / bodystyle`을 합쳐 한 개의 `content[]` 항목을 만든다(`rich_blocks.py:760`). 이 단계에서 자동으로 다음이 일어난다.

- `requestid`에 시스템 키(`cubeuniquename, cubechannelid, cubeaccountid, cubelanguagetype, cubemessageid`)가 자동 합쳐진다.
- 어떤 Block이라도 `bodystyle == "grid"`면 컨테이너 전체가 `"grid"`로 승격된다.
- `callback_address`가 비어 있지 않으면 `callbacktype="url"`이 자동 설정된다.

`build_richnotification(...)`이 마지막으로 봇 자격 증명(`from`, `token`, `fromusername`)과 수신자(`to.uniquename`, `to.channelid`)를 채워 최종 payload를 만든다.

### 2.6 client.py가 Cube에 POST 한다

`api/cube/client.py:94` `send_richnotification_blocks()`는 `requestid`가 하나라도 있으면 `CUBE_RICHNOTIFICATION_CALLBACK_URL`을 자동으로 콜백 주소로 주입한다. 즉 워크플로 코드는 보통 콜백 URL을 신경 쓸 필요가 없다.

### 2.7 사용자 응답(콜백) 흐름

사용자가 버튼/체크박스 등을 누르면 Cube가 `CUBE_RICHNOTIFICATION_CALLBACK_URL`로 콜백을 보낸다. 이 페이로드는 `api/cube/payload.py`의 `extract_cube_request_fields()`가 다시 일반 메시지처럼 변환해 워크플로에 흘려보낸다(`_extract_callback_message_lines`이 `requestid: 값` 형식으로 평탄화). 즉 워크플로 입장에서는 사용자가 **"PDF (pdf)"** 라고 입력한 것과 동일하게 보인다.

---

## 3. 의도(BlockIntent) 종류별 매핑표

| BlockIntent      | rich_blocks 헬퍼     | 의미                              | LLM이 채울 수 있나? |
| ---------------- | -------------------- | --------------------------------- | ------------------- |
| `TextIntent`     | `add_text`           | 평문 (multimessage 후보)          | O                   |
| `TableIntent`    | `add_table`          | 헤더 + 행 grid                    | O                   |
| `ImageIntent`    | `add_image`          | 이미지 + linkurl                  | O                   |
| `ChoiceIntent`   | `add_choice`         | 라디오/체크박스 + alertmsg        | O                   |
| `InputIntent`    | `add_input`          | 한 줄 텍스트 입력                 | O                   |
| `DatePickerIntent` | `add_datepicker`   | 날짜 선택                         | O                   |
| `RawBlockIntent` | `Block(...)` 직접    | 위로 표현 못 하는 케이스의 escape | **X (워크플로 전용)** |

`RawBlockIntent`는 `BlockIntent` 디스크리미네이티드 유니언에는 들어가지만, **시스템 프롬프트의 LLM 가이드에는 일부러 노출하지 않는다**(`api/cube/intents.py:71`). LLM이 이 escape hatch로 도망가지 않게 하려는 의도다.

---

## 4. 워크플로 작성 시 신경 써야 할 점

### 4.1 raw JSON을 직접 만들지 마라

`rows = [{"column": [{"type": "label", ...}]}]` 같은 dict를 직접 조립하지 말 것. 다음 우선순위로 작성한다.

1. **기존 `BlockIntent` 타입**(TextIntent/ChoiceIntent/...) 으로 표현 가능한가?
2. 안 되면, **새 `BlockIntent` 타입을 추가**할 가치가 있는가? (다른 워크플로도 재사용하나?)
3. 둘 다 아니면 비로소 `RawBlockIntent`를 사용하되, `rich_blocks.add_*`가 만들어 내는 row 형태를 그대로 채운다.

### 4.2 평문은 가능한 한 TextIntent로 두라

`TextIntent`만 있는 응답은 multimessage 경로로 가서 채팅처럼 보인다. 모두 다 구조 블록으로 만들면 한 풍선이 너무 무거워지고, 화면에서도 카드 UI가 과하다. **레이아웃이 필수이거나 사용자 입력이 필요한 부분만** 구조 블록으로 승격한다(`api/llm/prompt/system.py:20`의 [블록 종류 선택] 규칙과 동일).

### 4.3 5개 언어 배열을 신경 쓰지 마라 — 단, 리스트로 넘길 때는 주의

Cube는 `text` 필드를 5개 언어 배열로 요구한다. `_lang5()`가 자동으로 `["text", "", "", "", ""]`로 패딩해 주므로 **헬퍼에는 그냥 문자열을 넘기면 된다**. 단:

- 다국어를 직접 지정하려면 `[ko, en, zh, ja, ...]` **5개 정확히** 맞춰서 리스트로 넘긴다 — 부족하면 빈 문자열로 패딩되고, 초과하면 잘린다.
- `RawBlockIntent`를 직접 채우는 경우에는 손수 `_lang5()`를 호출하거나 5-원소 배열을 직접 만들어야 한다.

### 4.4 processid는 콜백의 키다

`ChoiceIntent`, `InputIntent`, `DatePickerIntent`는 `processid`를 가진다. 사용자가 응답하면 콜백 페이로드의 `resultdata[].requestid`로 이 값이 돌아온다. **같은 메시지 안에서는 처리 ID를 겹치지 않게** 짓고, 워크플로가 응답을 식별할 수 있도록 의미 있는 이름을 쓴다(`SelectFormat`, `ApprovalDecision` 등). 시스템 예약 키 (`cubeuniquename`, `cubechannelid`, `cubeaccountid`, `cubelanguagetype`, `cubemessageid`) 와는 절대 겹치지 않게 한다.

### 4.5 required + alertmsg는 같이 다닌다

`ChoiceIntent.required=True`처럼 필수 입력으로 만들면, `add_*` 헬퍼는 `mandatory: [{processid, alertmsg}]`를 자동 생성한다. `alertmsg`를 비워 두면 fallback으로 질문/라벨 텍스트가 들어간다. **필수가 아닌 항목까지 required=True로 두는 실수에 주의** — 사용자가 콜백을 보낼 수 없게 된다.

### 4.6 콜백 URL은 자동 — 단, requestid가 있어야 한다

`send_richnotification_blocks`는 Block 중 하나라도 `requestid`를 가지면 `CUBE_RICHNOTIFICATION_CALLBACK_URL`을 자동 주입한다(`client.py:111`). 즉 사용자 입력(choice/input/date)을 포함하면 콜백은 자동으로 동작한다. 반대로 콜백이 필요한데 표시만 되고 응답이 안 들어온다면 다음을 확인:

- intent에 `processid`가 비어 있지 않은가?
- `add_*` 호출에서 `requestid=[processid]`가 빠지지 않았는가? (헬퍼를 쓰면 자동으로 채워진다)
- `CUBE_RICHNOTIFICATION_CALLBACK_URL` 환경 변수가 설정돼 있는가?

### 4.7 텍스트와 구조 블록이 섞이면 호출이 쪼개진다

cube/service.py가 연속된 `TextIntent`만 한 multimessage로 묶고, 구조 블록은 별도 richnotification 호출로 보낸다. 즉 `[Text, Choice, Text]`는 multimessage → richnotification(choice) → multimessage 순으로 **세 번** Cube를 친다. 의도적이라면 그대로 두고, **한 풍선으로 모으고 싶다면 모든 항목을 구조 블록으로 만들거나** TextIntent 대신 `make_label_cell` 행을 같은 컨테이너에 넣는다.

### 4.8 한국어 메시지

Cube는 한국어 사용자 환경이다. 라벨, 질문, alertmsg, placeholder 모두 한국어로 작성한다. 영어 키워드(`processid`, `value`)는 시스템 식별자라 그대로 두지만, **사용자 눈에 보이는 텍스트는 모두 한국어**다.

### 4.9 표(Table)는 grid 모드를 자동으로 켠다

`add_table`은 `Block.bodystyle="grid"`로 반환되고, `add_container`가 컨테이너 전체를 grid로 승격한다(`rich_blocks.py:779`). **한 컨테이너에 표와 일반 폼을 섞지 마라** — 다른 항목까지 grid 레이아웃의 영향을 받는다. 표를 별도 의도 그룹으로 분리해 두 번에 나눠 보내는 편이 안전하다.

### 4.10 응답이 평문 fallback으로 떨어지는 케이스를 알아 두자

LLM이 잘못된 JSON을 뱉으면 `api/llm/service.py`의 `generate_reply_intent`는 다음 순서로 회복한다.

1. `function_calling` 구조화 실패 → 평문에서 JSON 추출 시도(중괄호 균형, trailing comma 제거, bare key 따옴표 보정 등 `_jsonish_variants`).
2. 그래도 안 되면 **평문 전체를 `TextIntent` 하나로 감싸** 사용자에게 문장으로라도 응답.
3. 단, 응답 텍스트가 ReplyIntent 형태(`"blocks":` / `"kind":` 패턴)인데 검증에 실패한 경우엔 디버깅 흔적이 사용자에게 그대로 노출되지 않도록 안내 문구로 대체한다.

이 폴백은 안전망이지 정상 경로가 아니다. **LLM 응답이 자주 폴백으로 떨어진다면** 시스템 프롬프트(`api/llm/prompt/system.py`)의 [출력 규칙]/[허용 스키마]가 모델 버전과 어긋난 것일 가능성이 크니 그쪽을 먼저 확인한다.

### 4.11 대화 이력에는 텍스트 다이제스트가 저장된다

구조 블록은 `intents_to_history_text()`로 한국어 다이제스트(`"[표 ...] 헤더: ... (3행)"`)로 변환되어 저장된다(`api/cube/service.py:512`). LLM이 다음 턴에서도 "지난 메시지에서 PDF/엑셀 중 PDF를 골랐었지" 같은 맥락을 유지하려면 이 변환이 사람도 LLM도 읽을 수 있어야 한다. **새 `BlockIntent` 타입을 추가하면 `intents_to_history_text()`도 같이 업데이트**해야 한다(`api/cube/intent_renderer.py:69`).

### 4.12 RawBlockIntent를 쓰는 마지막 수단

진짜 표현 못 하는 케이스(예: 특수 popupoption, 5-언어 다국어 라벨 등)는 `RawBlockIntent`를 워크플로 코드에서 만들어 넣는다. **LLM 시스템 프롬프트에는 노출되지 않으므로** LLM이 이걸 채워 보내는 일은 없다. 사용 시:

```python
from api.cube import rich_blocks
from api.cube.intents import RawBlockIntent

block = rich_blocks.add_table(headers=["A", "B"], rows=[["1", "2"]])
intent = RawBlockIntent(
    rows=block.rows,
    mandatory=block.mandatory,
    requestid=block.requestid,
    bodystyle=block.bodystyle,
)
```

`Block` → `RawBlockIntent`로 변환해 `reply_intents`에 넣으면 `intent_renderer`가 그대로 다시 `Block`으로 풀어낸다. 즉 워크플로가 `rich_blocks` 헬퍼 결과를 의도 리스트에 흘려보낼 때 쓰는 통로다.

---

## 5. 빠른 체크리스트 (워크플로 PR 머지 전)

- [ ] 노드가 raw dict가 아닌 `BlockIntent` 객체를 만든다.
- [ ] 평문 응답은 `TextIntent`로 둔다 — 모든 응답을 구조 블록으로 만들지 않았다.
- [ ] 사용자 입력 블록의 `processid`가 다른 블록과 겹치지 않는다.
- [ ] 시스템 예약 requestid (`cubeuniquename` 등) 와 충돌하지 않는다.
- [ ] `required=True`로 둔 항목은 정말 필수인지 확인했다.
- [ ] 한 컨테이너에 `add_table`과 폼 블록을 섞지 않았다(grid 부작용).
- [ ] 새 `BlockIntent` 타입을 추가했다면 `intents_to_history_text()`에도 케이스를 추가했다.
- [ ] 사용자에게 보이는 라벨/질문/alertmsg/placeholder가 모두 한국어다.
- [ ] LLM이 직접 채우는 의도라면 시스템 프롬프트의 [허용 스키마] 예시에도 등록했다.

---

## 6. 참고 자료

- 의도 스키마: `api/cube/intents.py`
- 의도 → Block 렌더러: `api/cube/intent_renderer.py`
- Block / 컨테이너 / payload 빌더: `api/cube/rich_blocks.py`
- 의도 그룹핑·전송 로직: `api/cube/service.py:353` (`_send_intent_reply`)
- HTTP 호출 + 콜백 URL 자동 주입: `api/cube/client.py:94` (`send_richnotification_blocks`)
- LLM 의도 파싱 + 폴백: `api/llm/service.py:61` (`generate_reply_intent`)
- LLM 시스템 프롬프트: `api/llm/prompt/system.py`
- 콜백 페이로드 평탄화: `api/cube/payload.py:40` (`_extract_callback_message_lines`)
