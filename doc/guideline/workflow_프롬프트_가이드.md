# 워크플로 프롬프트 관리 가이드

이 문서는 각 워크플로 패키지 안에서 LLM 프롬프트를 어떻게 정의하고 사용할지 팀원용으로 정리한 안내서입니다.

## 한눈에 보는 원칙

- LLM이 읽는 문자열(system / user 프롬프트)은 모두 각 워크플로 패키지 안의 `prompts.py` 한 곳에 모읍니다.
- `prompts.py`는 "LLM이 보는 것"만 담습니다. 코드가 사용자에게 직접 돌려주는 한국어 reply 문자열(`_STOP_REPLY`, `_ASK_*_REPLY` 등)은 해당 노드 파일 안에 남겨 둡니다.
- 워크플로 간 프롬프트를 공유하지 않습니다. 각 `prompts.py`는 그 워크플로에 한정된 자립적(self-contained) 자산입니다.
- 네이밍 규칙은 세 가지뿐입니다.
  - `<목적>_SYSTEM_PROMPT` — LLM system 메시지
  - `<목적>_USER_PROMPT_PREFIX` — JSON/payload 앞에 붙이는 고정 문자열
  - `<목적>_CONTEXT_TEMPLATE` — `.format()`으로 변수 슬롯을 채우는 경우

## 왜 분리하는가

프롬프트를 노드 파일 안쪽에 `_` 접두 모듈 상수로 두면 처음에는 편합니다. 하지만 다음과 같은 문제가 반복됩니다.

- 프롬프트 튜닝이 필요한데 어느 파일을 봐야 할지 찾는 데 시간이 걸립니다.
- 같은 워크플로 안의 여러 노드가 비슷한 문구를 따로 들고 다니면 드리프트가 생깁니다.
- 리뷰 시 프롬프트 변경과 로직 변경이 한 diff에 섞여 의도 파악이 어려워집니다.

`prompts.py`에 모으면 프롬프트 diff가 독립적으로 보이고, 튜닝과 A/B 테스트의 출발점이 한 파일로 고정됩니다.

## 디렉터리 구조

```
api/workflows/<workflow_id>/
├── __init__.py
├── lg_graph.py
├── lg_state.py
├── llm_decision.py
├── prompts.py           ← 이 파일
└── ...
```

## 네이밍 규칙 상세

### 1. `<목적>_SYSTEM_PROMPT`

LLM의 system 메시지로 들어가는 상수입니다. `.strip()`으로 양끝 공백을 제거해 저장합니다.

```python
TRANSLATOR_DECISION_SYSTEM_PROMPT = """
당신은 번역 워크플로를 제어하는 판단기입니다.
...
""".strip()
```

여러 개의 system 프롬프트가 필요하면 목적을 이름에 반영합니다. 예) `TRANSLATOR_DECISION_SYSTEM_PROMPT`, `TRANSLATION_SYSTEM_PROMPT`.

### 2. `<목적>_USER_PROMPT_PREFIX`

user 프롬프트 앞에 고정으로 붙이는 문자열입니다. 뒤에 JSON payload 같은 동적 내용을 `+` 연산자로 이어 붙일 때 사용합니다.

```python
TRANSLATOR_DECISION_USER_PROMPT_PREFIX = "현재 번역 워크플로 상태를 보고 다음 행동을 판단하세요.\n"
```

호출 시:

```python
user_prompt=(
    TRANSLATOR_DECISION_USER_PROMPT_PREFIX
    + json.dumps(state_payload, ensure_ascii=False, indent=2)
)
```

**주의:** payload에 `{`, `}`가 들어갈 수 있는 경우(JSON 등)는 반드시 `.format()`이 아니라 문자열 concat으로 처리해야 합니다. f-string은 템플릿이 정의 시점에 평가되므로 `prompts.py`에서 쓸 수 없습니다.

### 3. `<목적>_CONTEXT_TEMPLATE`

`.format(**kwargs)`로 변수 슬롯을 채우는 템플릿입니다. 값이 자연어일 때만 이 형태를 사용합니다. JSON/코드 등 `{` `}`가 포함될 수 있는 값은 prefix 패턴을 쓰세요.

```python
START_CHAT_CONTEXT_TEMPLATE = """\
아래 참고 자료를 바탕으로 사용자 질문에 답변하세요.

[참고 자료]
{contexts}

[질문]
{question}"""
```

호출 시:

```python
user_prompt=START_CHAT_CONTEXT_TEMPLATE.format(contexts=ctx, question=q)
```

## `prompts.py`에 넣지 않는 것

다음은 의도적으로 `prompts.py`에 넣지 않습니다.

- **사용자에게 직접 반환하는 reply 상수**: `_STOP_REPLY`, `_ASK_TARGET_REPLY`, `CANCEL_GUIDE_REPLY` 같은 Korean 문장. LLM을 거치지 않고 코드가 직접 사용자에게 돌려주는 문자열이므로, 해당 노드 파일(`llm_decision.py` 등)에 남겨 둡니다.
- **정규식/파싱 리터럴**: `_FOLLOW_UP_SOURCE_PATTERNS` 같은 규칙 기반 텍스트는 파싱 로직 근처에 둡니다.
- **에러 메시지/예외 문구**: `raise ValueError("...")` 안의 문자열은 이동시키지 않습니다.

"LLM이 읽는 문자열이면 `prompts.py`, 그 외에는 그대로" — 이 한 줄만 기억하면 됩니다.

## 참고 구현

- `api/workflows/start_chat/prompts.py` — system prompt + `CONTEXT_TEMPLATE` 혼합 예시
- `api/workflows/translator/prompts.py` — 한 워크플로에 system prompt 두 개(`DECISION`, `TRANSLATION`) + prefix 패턴
- `api/workflows/travel_planner/prompts.py` — system prompt + prefix 최소 구성

## 체크리스트

새 워크플로에 프롬프트를 추가할 때 확인할 항목입니다.

- [ ] `api/workflows/<workflow_id>/prompts.py`를 만들었는가
- [ ] system 프롬프트는 `.strip()`으로 저장했는가
- [ ] JSON payload를 붙일 때 `.format()` 대신 prefix + concat을 썼는가
- [ ] 사용자 직접 반환 reply는 `prompts.py`에 넣지 않고 노드 파일에 남겼는가
- [ ] import 경로는 절대 경로(`from api.workflows.<workflow_id>.prompts import ...`)로 썼는가
- [ ] 기존 인라인 상수(`_WORKFLOW_SYSTEM_PROMPT` 등)를 삭제했는가
- [ ] 관련 워크플로 테스트를 다시 돌려 통과를 확인했는가
