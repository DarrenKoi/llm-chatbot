---
tags: [concept, workflow, prompts, llm]
level: beginner
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/workflow_프롬프트_가이드.md
  - api/workflows/start_chat/prompts.py
  - api/workflows/translator/prompts.py
---

# 워크플로 프롬프트 관리 (Workflow Prompting)

> LLM 이 읽는 문자열은 워크플로 패키지의 `prompts.py` 한 곳에 모은다. 코드가 사용자에게 직접 돌려주는 한국어 reply 는 노드 파일에 남긴다.

## 왜 필요한가? (Why)

- 프롬프트가 노드 파일 안에 `_FOO_PROMPT` 같은 모듈 상수로 흩어지면 튜닝할 때 어디를 봐야 할지 찾는 데만 시간이 걸린다.
- 같은 워크플로 안에서 비슷한 문구를 여러 노드가 따로 들고 다니면 드리프트(drift)가 생긴다.
- 리뷰 시 프롬프트 변경과 로직 변경이 한 diff 에 섞이면 의도 파악이 어렵다.
- 비슷한 다른 개념과의 차이: 일반적인 i18n string table 과 달리 `prompts.py` 는 사용자가 보는 텍스트가 아니라 **LLM 만 보는** 텍스트만 담는다.

## 핵심 개념 (What)

### 정의

`prompts.py` 는 **LLM 이 system/user 메시지로 읽는 문자열만** 모은 워크플로 내부 모듈이다. 워크플로 간 공유는 하지 않는다 (`raw/learning-logs/workflow_프롬프트_가이드.md` §한눈에 보는 원칙).

### 관련 용어

- `<목적>_SYSTEM_PROMPT`: LLM system 메시지. `.strip()` 로 양끝 공백 제거.
- `<목적>_USER_PROMPT_PREFIX`: user 프롬프트 앞에 고정으로 붙이는 문자열. JSON payload 등 `{}` 가 들어가는 동적 값과 `+` 로 이어 붙일 때 사용.
- `<목적>_CONTEXT_TEMPLATE`: `.format(**kwargs)` 로 슬롯을 채우는 템플릿. 슬롯 값이 자연어일 때만 사용.
- `노드 reply 상수`: `_STOP_REPLY`, `_ASK_TARGET_REPLY` 등 — 코드가 LLM 없이 직접 사용자에게 돌려주는 한국어. **`prompts.py` 에 넣지 않는다.**

### 시각화 / 모델

```text
api/workflows/<workflow_id>/
├── __init__.py
├── lg_graph.py
├── lg_state.py
├── llm_decision.py            ← reply 상수(_STOP_REPLY 등) 위치
├── prompts.py                 ← LLM 이 읽는 문자열만
└── ...
```

```text
[ LLM 이 읽는 문자열 ]                     [ 사용자에게 직접 가는 문자열 ]
prompts.py                                노드 파일 (예: llm_decision.py)
  ├ TRANSLATOR_DECISION_SYSTEM_PROMPT     ├ _STOP_REPLY
  ├ TRANSLATOR_DECISION_USER_PROMPT_PREFIX├ _ASK_TARGET_REPLY
  └ START_CHAT_CONTEXT_TEMPLATE           └ CANCEL_GUIDE_REPLY
```

## 어떻게 사용하는가? (How)

### 최소 예제

**system prompt + JSON payload:**

```python
# api/workflows/sample_flow/prompts.py
SAMPLE_DECISION_SYSTEM_PROMPT = """
당신은 sample_flow 워크플로의 다음 행동을 판단하는 결정기입니다.
누락된 슬롯이 있으면 그 슬롯 이름을 반환합니다.
""".strip()

SAMPLE_DECISION_USER_PROMPT_PREFIX = "현재 워크플로 상태를 보고 다음 행동을 결정하세요.\n"
```

```python
# api/workflows/sample_flow/llm_decision.py
import json
from api.workflows.sample_flow.prompts import (
    SAMPLE_DECISION_SYSTEM_PROMPT,
    SAMPLE_DECISION_USER_PROMPT_PREFIX,
)

def decide(state):
    payload = {"source_text": state.get("source_text"), ...}
    user_prompt = (
        SAMPLE_DECISION_USER_PROMPT_PREFIX
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return llm_call(system=SAMPLE_DECISION_SYSTEM_PROMPT, user=user_prompt)
```

**자연어 슬롯 채우기 (`CONTEXT_TEMPLATE`):**

```python
# api/workflows/start_chat/prompts.py 예시
START_CHAT_CONTEXT_TEMPLATE = """\
아래 참고 자료를 바탕으로 사용자 질문에 답변하세요.

[참고 자료]
{contexts}

[질문]
{question}"""
```

```python
user_prompt = START_CHAT_CONTEXT_TEMPLATE.format(contexts=ctx, question=q)
```

### 실무 패턴

- **system prompt 는 `.strip()` 으로 저장** — 의도치 않은 선행/후행 공백 제거.
- **JSON payload 를 붙일 때 `.format()` 금지** — payload 안의 `{`, `}` 가 placeholder 로 해석되어 깨진다. **prefix + concat** 패턴을 사용.
- **f-string 금지** — 모듈 로드 시점에 평가되어 빈 변수로 굳어진다.
- **여러 system prompt 가 필요하면 목적을 이름에**: `TRANSLATOR_DECISION_SYSTEM_PROMPT`, `TRANSLATION_SYSTEM_PROMPT` 처럼 분리.
- **참고 구현** (`raw/learning-logs/workflow_프롬프트_가이드.md` §참고 구현):
  - `api/workflows/start_chat/prompts.py` — system prompt + `CONTEXT_TEMPLATE` 혼합 예시
  - `api/workflows/translator/prompts.py` — 한 워크플로에 system prompt 두 개(`DECISION`, `TRANSLATION`) + prefix 패턴
- **import 는 절대 경로**: `from api.workflows.<workflow_id>.prompts import ...`

### 주의사항 / 함정

- **`prompts.py` 에 넣지 말 것**:
  - 사용자에게 직접 반환하는 reply 상수 (`_STOP_REPLY`, `CANCEL_GUIDE_REPLY` 등)
  - 정규식·파싱 리터럴 (`_FOLLOW_UP_SOURCE_PATTERNS` 같은 것)
  - 에러/예외 메시지 문자열
- **워크플로 간 프롬프트 공유 금지** — 각 `prompts.py` 는 자립적. 비슷한 system prompt 가 두 워크플로에 필요해도 복사한다.
- **인라인 상수를 남겨 두기 쉬운 함정**: `prompts.py` 로 옮긴 뒤 노드 파일에 옛 `_WORKFLOW_SYSTEM_PROMPT` 가 남아 있으면 어느 쪽이 실제로 쓰이는지 헷갈린다 — 옮기면 원본을 지운다.
- **한 줄 룰**: "LLM 이 읽는 문자열이면 `prompts.py`, 그 외는 그대로." 다른 모든 규칙은 이 한 줄에서 파생된다.

### 체크리스트

- [ ] `api/workflows/<workflow_id>/prompts.py` 가 존재
- [ ] system 프롬프트는 `.strip()` 적용
- [ ] JSON payload 에는 `.format()` 대신 prefix + concat
- [ ] 사용자 직접 반환 reply 는 노드 파일에 남아 있음
- [ ] 절대 import 사용
- [ ] 옛 인라인 상수 삭제
- [ ] 관련 워크플로 테스트 통과

## 참고 자료 (References)

- 원본 메모: [../../raw/learning-logs/workflow_프롬프트_가이드.md](../../raw/learning-logs/workflow_프롬프트_가이드.md)
- 관련 개념:
  - [workflow-authoring.md](workflow-authoring.md) — 새 워크플로 작성 절차
  - [workflow-state-management.md](workflow-state-management.md) — 상태 분리 원칙
- 코드 경로:
  - `api/workflows/start_chat/prompts.py`
  - `api/workflows/translator/prompts.py`
