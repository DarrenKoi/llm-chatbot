# 워크플로 추가 가이드

이 문서는 이 저장소에서 새 워크플로를 효율적으로 만드는 표준 절차를 팀원용으로 정리한 안내서입니다.

## 한눈에 보는 원칙

- 이 저장소의 새 워크플로는 바로 `api/workflows/`에 만들지 않고 `devtools/workflows/`에서 먼저 작성합니다.
- 워크플로 이름은 `workflow_id` 하나로 통일하고, 디렉터리명·모듈명·MCP 파일명까지 같은 값으로 맞춥니다.
- 워크플로 구현은 작은 노드 여러 개로 나누고, 노드 하나에는 한 가지 책임만 두는 편이 유지보수에 유리합니다.
- 멀티턴 대화가 필요하면 임의 상태 저장 로직을 덕지덕지 붙이기보다 LangGraph의 `interrupt`와 `resume` 흐름으로 설계합니다.
- 운영 반영은 수동 복사가 아니라 `promote` 스크립트로 처리합니다.

## 현재 저장소의 표준 작업 순서

1. `workflow_id`를 정합니다.
2. `new_workflow` 스크립트로 dev 워크플로를 생성합니다.
3. `lg_state.py`와 `lg_graph.py`를 구현합니다.
4. 필요하면 dev MCP 도구를 연결합니다.
5. dev runner에서 대화 흐름과 상태 전이를 검증합니다.
6. 테스트를 추가하고 실행합니다.
7. `promote` 스크립트로 운영 경로에 반영합니다.

이 순서를 지키면 실험 코드와 운영 코드를 분리하면서도 등록 실수를 줄일 수 있습니다.

## 1. `workflow_id`를 먼저 설계하는 이유

현재 설정에서는 `workflow_id`가 아래 항목의 기준점 역할을 합니다.

- 워크플로 디렉터리 경로가 됩니다.
- 레지스트리에 등록되는 식별자가 됩니다.
- `handoff_keywords`가 매칭되면 `start_chat`이 넘기는 대상 이름이 됩니다.
- dev MCP 파일명과 운영 MCP 파일명 기준이 됩니다.

따라서 이름은 처음부터 소문자 `snake_case`로 정하고, 의미가 분명한 업무 단위로 짓는 편이 좋습니다.

좋은 예시는 `translator`, `travel_planner`, `invoice_summary` 같은 이름입니다.

피해야 할 예시는 `test`, `newflow`, `temp_work`, `myWorkflow` 같은 이름입니다.

## 2. devtools에서 스캐폴딩하는 방법

새 워크플로는 아래 명령으로 시작합니다.

```bash
python -m devtools.scripts.new_workflow sample_flow
```

이 명령은 현재 템플릿 기준으로 아래 파일을 생성합니다.

```text
devtools/workflows/sample_flow/
├── __init__.py
├── lg_graph.py
└── lg_state.py

devtools/mcp/sample_flow.py
```

이 방식의 장점은 시작 파일 구성이 팀 공통 규칙에 맞춰 고정된다는 점입니다.

## 3. 생성 직후 확인해야 하는 파일

### `devtools/workflows/<workflow_id>/__init__.py`

이 파일은 레지스트리가 읽는 진입점입니다.

현재 템플릿은 아래와 비슷한 형태입니다.

```python
def build_lg_graph():
    from .lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "sample_flow",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": (),
    }
```

이 파일에서 중요한 점은 `get_workflow_definition()`을 반드시 제공해야 한다는 점입니다.

### `devtools/workflows/<workflow_id>/lg_state.py`

이 파일은 LangGraph 상태를 정의하는 곳입니다.

공통 채팅 상태를 재사용하되, 이 워크플로에만 필요한 슬롯만 추가하는 방식이 좋습니다.

예를 들어 사용자가 여러 턴에 걸쳐 채워야 하는 값은 명시적인 필드로 두는 편이 좋습니다.

### `devtools/workflows/<workflow_id>/lg_graph.py`

이 파일은 실제 노드와 그래프 구조를 정의하는 곳입니다.

처음부터 복잡하게 만들기보다 진입 노드, 슬롯 수집 노드, 완료 노드 정도로 최소 구조를 먼저 세우는 편이 빠릅니다.

### `devtools/mcp/<workflow_id>.py`

이 파일은 dev 환경에서 쓸 MCP 서버와 도구 등록을 담당합니다.

운영 반영 시 같은 이름으로 `api/mcp/` 아래로 이동하므로 파일명과 역할을 일치시켜 두는 편이 좋습니다.

## 4. 효과적으로 설계하는 방법

### 상태는 작게 시작합니다

- 상태 필드는 실제로 여러 턴에서 다시 참조할 값만 둡니다.
- 사용자 메시지에서 즉시 계산 가능한 값은 굳이 상태에 오래 보관하지 않는 편이 좋습니다.
- 같은 의미의 필드를 중복해서 두지 않는 편이 좋습니다.

예를 들어 번역 워크플로라면 `source_text`, `target_language`, `last_asked_slot` 정도면 충분한 경우가 많습니다.

### 노드는 책임을 분리합니다

- 입력 해석 노드는 입력만 해석합니다.
- 외부 도구 호출 노드는 도구 호출만 담당합니다.
- 최종 응답 생성 노드는 답변 메시지 조립만 담당합니다.

이렇게 나누면 디버깅과 테스트가 쉬워집니다.

### 분기 기준은 코드로 설명 가능해야 합니다

조건 분기가 많아질수록 한 노드에서 모든 것을 처리하지 말고, 분기 판단 함수와 실제 실행 노드를 분리하는 편이 좋습니다.

### 멀티턴은 `interrupt/resume`으로 설계합니다

현재 저장소는 LangGraph 기반 멀티턴 흐름을 전제로 하고 있으므로, 누락 슬롯 확인과 후속 질문은 `interrupt` 기반으로 설계하는 편이 가장 자연스럽습니다.

직접 세션 파일을 덧붙이는 방식보다 그래프 상태와 재개 흐름을 그대로 활용하는 편이 버그를 줄이기 좋습니다.

## 5. 구현할 때 지켜야 하는 현재 규칙

### 패키지 내부 import

워크플로 패키지 내부 import는 상대 import를 사용하는 편이 좋습니다.

```python
from .lg_state import SampleFlowState
from .nodes import collect_slot_node
```

이 규칙을 지켜야 dev 경로에서 운영 경로로 옮겨도 import 수정 범위가 줄어듭니다.

### MCP import

dev 단계에서는 템플릿처럼 `devtools.mcp.<workflow_id>`를 사용합니다.

`promote` 스크립트가 운영 반영 시 이 경로를 `api.mcp.<workflow_id>`로 자동 치환합니다.

### 도구 등록 호출 위치

도구가 필요한 워크플로라면 `build_lg_graph()` 경로에서 등록 함수를 한 번 호출하도록 두는 편이 현재 구조와 가장 잘 맞습니다.

실제 `translator` 워크플로도 `build_lg_graph()` 진입 시 번역 도구 등록을 수행합니다.

## 6. `handoff_keywords`를 정하는 방법

`handoff_keywords`는 `start_chat`에서 사용자 발화를 보고 어떤 서브워크플로로 넘길지 결정하는 기준입니다.

현재 구현은 사용자 메시지를 소문자로 바꾼 뒤, 키워드가 포함되어 있는지만 확인합니다.

따라서 키워드는 아래 원칙으로 정하는 편이 좋습니다.

- 너무 넓은 일반 단어는 피합니다.
- 업무 의미가 분명한 표현을 넣습니다.
- 한국어와 영어를 함께 쓰는 업무라면 두 언어를 같이 넣습니다.
- 이미 다른 워크플로가 쓰는 키워드와 겹치지 않게 조심합니다.

예를 들어 `번역`, `translate`, `translation` 정도는 괜찮지만 `문서`, `도움`, `계획` 같은 넓은 단어는 오분류를 일으키기 쉽습니다.

## 7. dev runner로 검증하는 방법

로컬 검증은 아래 명령으로 시작합니다.

```bash
python -m devtools.workflow_runner.app
```

이 runner는 `devtools/workflows/`를 자동 탐색해서 워크플로 목록을 구성합니다.

검증할 때는 아래 항목을 반드시 확인하는 편이 좋습니다.

- 첫 메시지에서 기대한 노드로 진입하는지 확인합니다.
- 누락 슬롯이 있을 때 질문이 자연스럽게 반환되는지 확인합니다.
- 다음 메시지에서 `resume`이 정상 동작하는지 확인합니다.
- 상태 패널에서 필드 값이 기대대로 쌓이는지 확인합니다.
- 완료 후 불필요한 상태가 남지 않는지 확인합니다.

## 8. 테스트를 붙이는 방법

문서만으로는 품질을 보장하기 어렵기 때문에 최소 테스트는 함께 추가하는 편이 좋습니다.

권장하는 최소 테스트 범위는 아래와 같습니다.

- 정상 완료 경로 테스트를 작성합니다.
- 필수 슬롯이 비어 있을 때 interrupt가 발생하는지 테스트합니다.
- 후속 입력으로 resume이 이어지는지 테스트합니다.
- 레지스트리에서 `workflow_id`를 정상 발견하는지 테스트합니다.

기본 실행 명령은 아래와 같습니다.

```bash
pytest tests/ -v
```

## 9. 운영 반영 방법

검증이 끝나면 아래 명령으로 운영 경로에 반영합니다.

```bash
python -m devtools.scripts.promote sample_flow
```

이 스크립트는 현재 설정 기준으로 아래 작업을 수행합니다.

1. `devtools/workflows/sample_flow/`를 `api/workflows/sample_flow/`로 복사합니다.
2. `devtools/mcp/sample_flow.py`를 `api/mcp/sample_flow.py`로 복사합니다.
3. `devtools.mcp.` import를 `api.mcp.` import로 자동 치환합니다.
4. import 검증을 수행합니다.
5. 검증이 통과하면 dev 원본을 삭제합니다.

즉, 운영 반영은 수동 복사보다 `promote` 스크립트로 처리하는 편이 안전합니다.

## 10. 팀에서 자주 실수하는 지점

- `workflow_id`와 디렉터리명을 다르게 만드는 실수를 합니다.
- `get_workflow_definition()`에서 `build_lg_graph`를 빠뜨리는 실수를 합니다.
- `handoff_keywords`를 너무 넓게 잡아 엉뚱한 요청이 라우팅되는 실수를 합니다.
- dev 단계에서 절대 import를 남겨 promotion 후 import 오류를 만드는 실수를 합니다.
- 도구 등록 함수는 만들었지만 실제 그래프 빌드 경로에서 호출하지 않아 런타임에 도구가 비어 있는 실수를 합니다.

## 11. 권장 체크리스트

- 새 워크플로는 `new_workflow`로 시작합니다.
- 상태 필드는 꼭 필요한 값만 둡니다.
- 노드는 한 가지 책임만 갖게 나눕니다.
- `handoff_keywords`는 좁고 구체적으로 정합니다.
- dev runner에서 멀티턴 흐름을 직접 확인합니다.
- 자동 테스트를 추가합니다.
- 운영 반영은 `promote`로 수행합니다.

이 체크리스트를 지키면 새 워크플로를 빠르게 만들면서도 현재 저장소 규칙과 충돌하지 않게 유지할 수 있습니다.
