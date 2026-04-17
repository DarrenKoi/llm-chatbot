# richnotification / multimessage 전송 전략

## 1. 배경

현재 Cube 응답은 `api/cube/payload.py`의 `build_richnotification_payload()`가 순수 텍스트 한 줄만 감싸서 보낸다. 하지만 LLM 응답에는 표, 코드, 이미지, 사용자 선택 유도 같은 다양한 콘텐츠가 섞여 있고, 이를 모두 평문으로 흘려보내면 다음 문제가 생긴다.

- 표/코드가 chat 클라이언트의 폰트·줄바꿈 때문에 깨져 보인다.
- 사용자에게 선택지를 제시하고 응답을 다시 받는 흐름을 만들 수 없다.
- 이미지·하이퍼링크 같은 구조적 UI 요소를 활용할 수 없다.

Cube 플랫폼은 이를 해결하기 위해 두 가지 전송 경로를 제공한다. 이 문서는 두 경로의 차이와, 앞으로 richnotification을 어떻게 도입·확장할지에 대한 설계 방향을 정리한다.

---

## 2. multimessage vs richnotification

두 엔드포인트는 "예쁜 메시지냐 아니냐"의 차이가 아니라, **정체성·수신자·상호작용성**이 근본적으로 다르다.

| 축 | multimessage | richnotification |
| --- | --- | --- |
| 자격 증명 | `CUBE_API_ID` + `CUBE_API_TOKEN` (시스템 계정) | `CUBE_BOT_ID` + `CUBE_BOT_TOKEN` (봇 인격, 5개 언어 `fromusername`) |
| 수신자 | `uniqueNameList[]`, `channelList[]` — 브로드캐스트 형태 | `uniquename: [user_id]` + `channelid: [channel_id]` — 단일 대화 |
| 페이로드 | 평문 한 줄 (`msg`) | `header / content[] / process / result` 트리 구조 |
| 상호작용 | 단방향. 사용자는 읽기만 가능 | 양방향. 버튼/셀렉트/입력이 `process.callbackaddress`로 회신 |
| 분할 | 길면 분할 필수 (`api/cube/chunker.py`의 40줄 기준) | 분할 불가. 한 블록이 한 메시지 |

### 설계상 중요한 포인트

- **자격 증명 분리는 보안 경계다.** multimessage의 API 토큰은 채널 어디로든 밀어넣을 수 있는 서버 계정 권한이고, 봇 토큰은 봇 인격 자체다. 사용자가 버튼을 눌러 답신할 수 있으려면 "어떤 봇에게 답하는지"가 정해져야 하므로, 콜백 구조는 반드시 봇 쪽(richnotification)에 붙는다.
- **richnotification이 존재하는 진짜 이유는 상호작용이다.** `processid`, `mandatory`, `requestid`, `callbackaddress` 같은 필드는 모두 클라이언트가 폼을 모아서 POST로 돌려보내기 위한 것이다. 이미지·표는 부수 효과에 가깝다.
- **라우팅 규칙은 이미 `chunker.py:42-57`에 녹아 있다.** 일반 텍스트 → `multi`, 코드 블록·표 → `rich`. 새로운 블록 종류(이미지, 선택지 등)는 `_Block.kind`를 확장하는 자연스러운 지점이다.

### 판단 원칙

> multimessage는 확성기, richnotification은 양식지.
>
> 정보를 방송하면 확성기, 사용자에게 무언가를 "묻거나" 특정 레이아웃이 아니면 의미가 훼손되면 양식지를 쓴다.

- 기본값은 multimessage. 저렴하고 안정적이며 스키마가 없어 LLM이 망가뜨릴 수 없다.
- richnotification으로 승격하는 기준은 다음 세 가지 중 하나에 해당할 때로 제한한다.
  1. **정확한 레이아웃이 필요할 때** (표, 이미지 크기 지정 등)
  2. **사용자 입력이 필요할 때** (셀렉트, 버튼, 날짜 선택 등)
  3. **원자적 전달이 필요할 때** (분할되면 의미가 깨지는 코드 블록·영수증 카드 등)

---

## 3. 도입 전략: **하이브리드 방식**

LLM이 richnotification JSON을 직접 만들게 하거나, 모든 레이아웃을 Python에 하드코딩하는 건 둘 다 나쁜 선택이다. 대신 역할을 쪼갠다.

### 역할 분담

- **Python = 스키마 권한자.** 블록 팩토리(`label()`, `button()`, `image()`, `table()`, `choice()`, `datepicker()` 등)가 규격을 보장한다. 5개 언어 배열 길이, 기본값 `active: true`, `processid` 네이밍 규칙, header/process 봉투 등은 Python이 전담한다.
- **LLM = 의도만 생성.** LLM은 richnotification 원본 스키마를 절대 보지 않는다. 대신 우리가 정의한 작은 의도 스키마(intent schema)에 맞춰 값을 채운다.
  ```python
  # 예시 — 의도 스키마
  {"kind": "table", "title": "...", "headers": [...], "rows": [[...]]}
  {"kind": "choice", "question": "...", "options": [{"label": "...", "value": "..."}], "multi": False}
  {"kind": "image", "source_url": "...", "alt": "..."}
  ```
- **Translator = 의도 → richnotification JSON.** 새 모듈(`api/cube/rich_blocks.py` 예정)이 의도 객체를 받아 Cube 규격의 `content[]` 트리로 변환한다.

### 왜 하이브리드인가

- 성능이 낮은 LLM을 염두에 두므로, 스키마 위반 위험을 최소화해야 한다. "5개 언어 배열", "같은 `processid`로 라디오 그룹 형성"(`richnotification_rule.txt:135`), "`mandatory`가 `processid`를 교차 참조"(rule.txt:338) 같은 비자명한 제약은 Python이 타입 체크로 잡는다.
- LLM은 "이건 표로 보여줘야 한다 / 선택지가 필요하다 / 그냥 평문이면 된다" 같은 **의미적 판단**에는 충분히 능하다. 이 판단만 맡기고 포맷 생성은 맡기지 않는다.
- 기존 `build_richnotification_payload()`가 이미 header/token 봉투를 소유하므로 확장 지점이 자연스럽다. LLM 컨텍스트에 `CUBE_BOT_TOKEN`이 노출되지 않는 보안 이점도 있다.

### 흐름 요약

```
LLM 응답
  ↓
워크플로(orchestrator)가 블록 의도 판별
  ├─ 평문 블록 → multimessage 경로 (기존 chunker)
  └─ 구조 블록(표/이미지/선택) → 의도 객체 생성
                                    ↓
                         rich_blocks translator가
                         richnotification JSON 변환
                                    ↓
                         send_richnotification 전송
```

---

## 4. 구현 계획

### 4.1 신규 모듈: `api/cube/rich_blocks.py`

블록 팩토리와 컴포저를 제공한다.

```python
def text_block(text: str) -> dict: ...
def table_block(headers: list[str], rows: list[list[str]]) -> dict       # bodystyle="grid"
def image_block(source_url: str, alt: str = "", *, inner: bool = True) -> dict: ...
def choice_block(
    question: str,
    options: list[tuple[str, str]],     # (label, value)
    *, processid: str = "Sentence", multi: bool = False,
) -> dict: ...
def input_block(
    prompt: str, *, processid: str = "Sentence",
    min_length: int = -1, max_length: int = -1,
) -> dict: ...
def datepicker_block(label: str, *, processid: str = "SelectDate", default: str = "") -> dict: ...

def compose(
    *blocks,
    callback_address: str | None = None,
    session_id: str = "", sequence: str = "1",
) -> dict:
    """여러 블록을 richnotification content[] + process 트리로 조립한다."""
```

내부 규약:
- 모든 문자열 필드는 "5개 언어 배열"로 자동 확장한다(`_lang5(text)`).
- `processid`는 `richnotification_rule.txt:368-394`의 관례를 상수로 제공한다.
- `mandatory` / `requestid`는 블록이 요구 여부를 스스로 알리게 하고, `compose()`가 취합한다.

### 4.2 `build_richnotification_payload()` 확장

현재 시그니처는 평문만 받는다. 문자열 또는 블록 리스트 모두 받을 수 있도록 오버로드한다. 기존 호출부는 그대로 동작한다(하위 호환).

```python
def build_richnotification_payload(
    *,
    user_id: str,
    channel_id: str,
    reply: str | list[dict],           # 평문 또는 블록 리스트
    callback_address: str | None = None,
) -> dict[str, Any]:
    ...
```

### 4.3 의도 스키마 + 워크플로 연결

- Pydantic 모델로 의도 스키마를 정의한다(`api/workflows/models.py`의 `WorkflowReply` 옆에 배치).
- 기존 워크플로는 평문 응답 + 블록 의도 리스트를 함께 반환할 수 있게 확장한다.
- `api/cube/chunker.py`의 `_Block.kind`에 `image`, `choice`, `input` 등을 추가해 블록 라우팅을 일관되게 만든다.
- LLM에 의도 생성을 시킬 때는 구조적 출력(structured output / tool calling)을 사용해 형식 이탈을 원천 차단한다.

### 4.4 단계별 롤아웃

| 단계 | 범위 | 목적 |
| --- | --- | --- |
| 1 | `rich_blocks.py` 최소 세트(text, table, image) + `build_richnotification_payload()` 확장 | 기존 라우팅(`chunker.py`의 table/code)을 하드코딩에서 블록 팩토리로 이관 |
| 2 | `choice_block` / `input_block` + 콜백 수신 라우터 | 사용자 선택·입력을 수집하는 워크플로 실험 (예: 목적지 선택, 보고서 형식 선택) |
| 3 | 의도 스키마 + 워크플로 연동 | LLM이 의도 단위로 응답하게 만들고, 라우팅을 한 곳(chunker+translator)으로 수렴 |
| 4 | `datepicker` / `list` / `container` 등 고급 블록 | 복잡한 양식형 UX 대응 |

---

## 5. 주의 사항

- `callbackaddress`는 클라이언트 네트워크에서 도달 가능해야 한다. 로컬 IP를 쓰지 않도록 `config` 기반으로만 주입한다.
- 이미지 URL은 DMZ 내부 여부에 따라 `location` / `inner` 값이 달라진다(`richnotification_rule.txt:233, 238`). 블록 팩토리가 기본값을 고르도록 한다.
- `mandatory.alertmsg`는 5개 언어 배열이다. 한국어 하나만 있어도 나머지 4개 슬롯을 채워야 한다.
- 분할이 불가하므로, richnotification 한 건에 너무 많은 블록을 담지 않는다. 긴 응답은 multimessage(본문) + richnotification(표·선택 UI) 조합으로 나눈다.
- 봇 토큰은 절대 LLM 프롬프트·로그에 노출하지 않는다. 봉투 생성은 Python 전용 경로에서만 이뤄져야 한다.

---

## 6. 참고

- 규격 원문: `richnotification_rule.txt`
- 예시: `richnotification_samples.md`
- 검증 체크리스트: `richnotification_test_checklist.md`
- 기존 라우팅: `api/cube/chunker.py`, `api/cube/client.py`, `api/cube/payload.py`
