---
tags: [concept, workflow, registry, handoff]
level: intermediate
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/workflow_등록_가이드.md
  - api/workflows/registry.py
  - api/workflows/start_chat/lg_graph.py
---

# 워크플로 등록 (Workflow Registration)

> 새 워크플로를 등록한다는 것은 중앙 목록을 수정하는 것이 아니라 "패키지 계약을 맞춰 자동 발견 구조에 태운다"는 의미다.

## 왜 필요한가? (Why)

- 워크플로가 늘어나도 공유 파일을 매번 수정하면 머지 충돌과 회귀 위험이 커진다.
- 워크플로 패키지를 자립적(self-contained)으로 만들면 팀별 ownership 이 깔끔해진다.
- 등록 실수의 원인을 한곳에 가두기 위해, "패키지 스캔 + 계약 검증 + 키워드 라우팅 + 도구 등록" 네 층이 명확히 분리되어 있어야 한다.
- 비슷한 다른 개념과의 차이: 일반적인 plugin 시스템과 달리 이 저장소는 별도 매니페스트 파일이 없고, Python 패키지 컨벤션 자체가 등록 메커니즘이다.

## 핵심 개념 (What)

### 정의

워크플로 등록은 다음 네 층의 조합이다 (`raw/learning-logs/workflow_등록_가이드.md` §1):

1. **패키지 발견** — `api/workflows/registry.py` 의 `discover_workflows()` 가 `api.workflows` 하위 서브패키지를 스캔.
2. **워크플로 정의 정규화** — `get_workflow_definition()` / `WORKFLOW_DEFINITION` 결과 검증 + 정규화.
3. **`start_chat` handoff 연결** — `handoff_keywords` 가 비어있지 않은 워크플로만 루트 그래프 서브그래프로 연결.
4. **MCP 도구 등록** — 그래프 빌드 경로에서 도구 등록 함수를 호출.

### 관련 용어

- `discover_workflows()`: `api.workflows` 패키지(또는 `devtools.workflows`) 하위를 스캔. 디렉터리가 패키지여야 하고, `_` 로 시작하면 건너뛴다.
- `get_workflow_definition() / WORKFLOW_DEFINITION`: 워크플로 메타데이터. `workflow_id`, `build_lg_graph`(callable), `handoff_keywords`, 선택적으로 `tool_tags` 를 담는다.
- `list_handoff_workflows()`: `handoff_keywords` 가 비어있지 않은 워크플로만 반환. `start_chat` 이 사용한다.
- `tool_tags`: MCP 도구 후보 필터링에 쓰일 수 있는 소문자 태그 (`translator` 는 `("translation", "language")`).
- `promote 스크립트`: `python -m devtools.scripts.promote <workflow_id>` — dev 패키지를 `api/` 로 복사 + `devtools.mcp.` → `api.mcp.` import 치환 + 검증 + 원본 삭제.

### 시각화 / 모델

```text
api/workflows/<workflow_id>/__init__.py
        │
        ├─ get_workflow_definition() → {workflow_id, build_lg_graph, handoff_keywords, tool_tags?}
        │
        ▼
discover_workflows()  →  registry (workflow_id 키)
        │
        ├─ list_handoff_workflows()  (handoff_keywords 비어있지 않은 것만)
        │       │
        │       ▼
        │   start_chat.classify_node  →  서브그래프로 분기
        │
        └─ build_lg_graph() 호출 시점에 register_*_tools() 호출  →  api/mcp/ 등록
```

## 어떻게 사용하는가? (How)

### 최소 예제

```python
# api/workflows/sample_flow/__init__.py

def build_lg_graph():
    from api.workflows.sample_flow.lg_graph import build_lg_graph as builder
    from api.workflows.sample_flow.tools import register_sample_tools  # 도구가 있을 때만

    register_sample_tools()
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "sample_flow",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": ("샘플 업무", "sample flow"),
        "tool_tags": ("sample",),  # 선택
    }
```

핵심:

- `workflow_id` 가 최종 등록 이름이며 디렉터리명·MCP 파일명과 같아야 한다.
- `build_lg_graph` 는 **callable** 이어야 한다 (값 자체를 그래프로 두면 안 됨).
- `handoff_keywords` 가 비어있으면 레지스트리에는 등록되지만 `start_chat` 자동 라우팅 대상은 아니다.
- `state_cls` 는 더 이상 필수가 아니며 정규화 과정에서 제거된다 (`raw/learning-logs/workflow_등록_가이드.md` §3).

### 실무 패턴

- **dev → 운영 리프트**: `devtools/workflows/<workflow_id>/` 에서 시작 → `python -m devtools.scripts.promote <workflow_id>` 가 운영 경로로 옮긴다 (`raw/learning-logs/workflow_등록_가이드.md` §10).
- **워크플로 전용 상태는 패키지 안 `lg_state.py`**: 공유 `api/workflows/lg_state.py` 에 추가하지 않는다 — [workflow-state-management.md](workflow-state-management.md) 참고.
- **도구 등록은 `build_lg_graph()` 경로에서**: 도구 등록 함수를 만들기만 하고 호출을 빠뜨리면 런타임에 도구가 비어 있다 (`translator` 는 `tools.py` 의 `register_translator_tools()` 를 빌드 시점에 호출).
- **키워드 설계는 사용자 발화에서 역으로**: 양성 예시(이 워크플로로 가야 하는 문장) + 음성 예시(비슷해 보이지만 다른 흐름으로 가야 하는 문장)를 같이 검증.

### 주의사항 / 함정

- **`workflow_id` 중복은 런타임 예외**: 같은 id 가 두 번 발견되면 레지스트리가 던진다. 디렉터리명·`workflow_id`·MCP 파일명을 모두 같은 값으로 묶어 두는 편이 안전하다.
- **first-match 라우팅 + 패키지 스캔 순서 의존**: `classify_node` 는 사용자 메시지를 소문자화한 뒤 `handoff_keywords` 를 앞에서부터 검사한다. 발견 순서는 패키지 스캔 순서를 따르므로, 키워드가 겹치면 먼저 발견된 워크플로가 매칭된다 (`raw/learning-logs/workflow_등록_가이드.md` §5).
- **나쁜 키워드 예시**: `도움`, `계획`, `문서`, `분석` 같은 범용 명사. 워크플로 의미가 드러나는 2~3 단어 표현을 우선.
- **자주 발생하는 실패 원인** (`raw/learning-logs/workflow_등록_가이드.md` §12):
  - 디렉터리가 패키지가 아니라 발견 실패
  - `get_workflow_definition()` 자체가 누락되어 건너뜀
  - `build_lg_graph` 가 callable 이 아님
  - `handoff_keywords` 누락으로 분기 안 됨
  - 도구 등록 함수가 정의만 되고 호출되지 않음
- **공유 파일은 건드리지 말 것**: `api/workflows/lg_state.py`, `registry.py` 는 새 워크플로 추가 시 손대지 않는 것이 원칙.

## 참고 자료 (References)

- 원본 메모: [../../raw/learning-logs/workflow_등록_가이드.md](../../raw/learning-logs/workflow_등록_가이드.md)
- 관련 개념:
  - [workflow-runtime-structure.md](workflow-runtime-structure.md) — 런타임 구조 전반
  - [workflow-state-management.md](workflow-state-management.md) — 패키지 내 상태 분리
  - [workflow-authoring.md](workflow-authoring.md) — 새 워크플로 작성 절차
  - [workflow-routing-scaling.md](workflow-routing-scaling.md) — `handoff_keywords` 의 한계와 확장 전략
- 코드 경로:
  - `api/workflows/registry.py`
  - `api/workflows/start_chat/lg_graph.py`
  - `api/workflows/translator/__init__.py`
  - `api/workflows/translator/tools.py`
  - `devtools/scripts/new_workflow.py`
  - `devtools/scripts/promote.py`
