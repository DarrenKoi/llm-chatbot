# 워크플로 등록 가이드

이 문서는 현재 저장소 설정에서 워크플로가 실제로 어떻게 등록되는지와, 팀원이 새 워크플로를 어떤 지점에 맞춰 연결해야 하는지를 설명하는 안내서입니다.

## 핵심 요약

- 현재 설정에서는 중앙 목록 파일에 워크플로를 수동으로 추가하지 않습니다.
- `api/workflows/<workflow_id>/` 아래에 패키지를 만들고 계약을 맞추면 `registry.py`가 자동으로 발견합니다.
- `handoff_keywords`가 비어 있지 않으면 `start_chat`이 그 워크플로를 handoff 대상으로 인식합니다.
- 외부 도구가 필요하면 `api/mcp/`와 연결하고, 그래프 빌드 경로에서 등록 함수를 호출해야 런타임에 사용할 수 있습니다.
- dev 단계에서는 같은 메커니즘을 `devtools/workflows/`와 `devtools/mcp/`에 대해 그대로 사용합니다.

## 1. 현재 등록 구조의 큰 그림

현재 워크플로 등록은 아래 네 층으로 나뉩니다.

1. 패키지 발견 단계가 있습니다.
2. 워크플로 정의 정규화 단계가 있습니다.
3. `start_chat` handoff 연결 단계가 있습니다.
4. MCP 도구 등록 단계가 있습니다.

즉, 단순히 디렉터리만 만든다고 끝나는 구조가 아니라, 패키지 계약과 런타임 연결 지점을 모두 맞춰야 정상 동작합니다.

## 2. 패키지 발견은 `api/workflows/registry.py`가 담당합니다

`api/workflows/registry.py`의 `discover_workflows()`는 `api.workflows` 패키지 아래 서브패키지를 스캔합니다.

현재 기준에서 자동 발견 규칙은 아래와 같습니다.

- 디렉터리가 패키지여야 합니다.
- 패키지 이름이 `_`로 시작하면 건너뜁니다.
- `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`이 있어야 합니다.
- `build_lg_graph`가 callable이어야 합니다.

즉, 새 워크플로를 등록하려면 우선 `api/workflows/<workflow_id>/__init__.py`가 이 계약을 만족해야 합니다.

## 3. 최소 등록 계약은 `__init__.py`에 있습니다

현재 설정에서는 아래 형태가 가장 단순한 등록 예시입니다.

```python
def build_lg_graph():
    from api.workflows.sample_flow.lg_graph import build_lg_graph as builder
    return builder()


def get_workflow_definition() -> dict[str, object]:
    return {
        "workflow_id": "sample_flow",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": ("샘플 업무", "sample flow"),
    }
```

이 예시에서 핵심은 아래와 같습니다.

- `workflow_id`가 최종 등록 이름입니다.
- `build_lg_graph`가 실제 그래프 빌더를 반환합니다.
- `handoff_keywords`는 루트 대화에서 이 워크플로로 보낼지 판단하는 기준입니다.

현재 `state_cls`는 필수가 아니며, 레지스트리 정규화 과정에서 제거됩니다.

## 4. `workflow_id`는 중복되면 안 됩니다

레지스트리는 최종적으로 `workflow_id`를 key로 사용합니다.

같은 `workflow_id`가 두 번 발견되면 런타임에서 예외가 발생합니다.

따라서 아래 항목은 모두 같은 이름으로 맞추는 편이 가장 안전합니다.

- 디렉터리명입니다.
- `workflow_id` 값입니다.
- dev MCP 파일명입니다.
- 운영 MCP 파일명입니다.

## 5. `handoff_keywords`가 실제 등록 범위를 결정합니다

현재 `start_chat` 루트 그래프는 `list_handoff_workflows()` 결과를 읽어 서브그래프를 붙입니다.

이 함수는 `handoff_keywords`가 비어 있지 않은 워크플로만 반환합니다.

즉, 같은 워크플로라도 아래처럼 동작 차이가 있습니다.

- `handoff_keywords`가 비어 있으면 레지스트리에는 등록되지만 `start_chat` 자동 라우팅 대상은 아닙니다.
- `handoff_keywords`가 있으면 `start_chat`이 분기 후보로 포함합니다.

현재 분류 방식은 단순 문자열 포함 검사이므로 키워드 설계가 매우 중요합니다.

## 6. 현재 `start_chat` 라우팅 방식

`api/workflows/start_chat/lg_graph.py`는 아래 순서로 동작합니다.

1. `list_handoff_workflows()`로 handoff 대상 워크플로를 읽습니다.
2. 각 워크플로의 `build_lg_graph()`를 호출해 서브그래프를 붙입니다.
3. 사용자 메시지를 소문자로 바꿉니다.
4. `handoff_keywords` 중 하나라도 포함되면 해당 `workflow_id`로 분기합니다.
5. 어떤 키워드도 맞지 않으면 일반 `start_chat` 응답 경로로 남습니다.

따라서 현재 설정에서 워크플로 등록은 사실상 `레지스트리 등록 + handoff 키워드 설계`의 조합이라고 보는 편이 정확합니다.

## 7. MCP 도구 등록은 별도 계층입니다

워크플로가 외부 도구를 써야 하면 워크플로 등록만으로는 충분하지 않습니다.

예를 들어 `translator`는 `api/workflows/translator/tools.py`에서 아래 항목을 등록합니다.

- MCP 서버를 등록합니다.
- MCP 도구 메타데이터를 등록합니다.
- 로컬 핸들러를 등록합니다.

그리고 이 등록 함수는 `api/workflows/translator/__init__.py`의 `build_lg_graph()` 경로에서 호출됩니다.

즉, 도구가 필요한 워크플로는 아래 구조를 맞추는 편이 좋습니다.

```python
def build_lg_graph():
    from api.workflows.sample_flow.lg_graph import build_lg_graph as builder
    from api.workflows.sample_flow.tools import register_sample_tools

    register_sample_tools()
    return builder()
```

이 호출이 빠지면 워크플로는 등록되어도 실행 중 사용할 도구가 비어 있을 수 있습니다.

## 8. `tool_tags`는 선택 사항이지만 현재 구조와 잘 맞습니다

레지스트리는 `tool_tags`도 정규화해서 보관합니다.

현재 코드에서는 이 값이 MCP 도구 후보 필터링에 사용될 수 있으므로, 도구 의존성이 분명한 워크플로라면 같이 넣는 편이 좋습니다.

예를 들어 번역 워크플로는 `("translation", "language")` 태그를 사용합니다.

태그는 소문자 기준으로 정리되므로, 표기 방식보다 의미 일관성이 더 중요합니다.

## 9. dev 환경 등록은 같은 구조를 `devtools/`에 적용합니다

로컬 개발 단계에서는 `devtools.workflow_runner.dev_orchestrator`가 `discover_workflows(package_name="devtools.workflows")`를 호출합니다.

즉, dev 환경도 운영과 같은 자동 발견 메커니즘을 사용합니다.

현재 dev 등록 흐름은 아래와 같습니다.

1. `devtools/workflows/<workflow_id>/`를 만듭니다.
2. `__init__.py`에서 `get_workflow_definition()`을 제공합니다.
3. 필요하면 `devtools/mcp/<workflow_id>.py`를 만듭니다.
4. dev runner가 목록을 다시 읽으면 자동으로 보입니다.

이 구조 덕분에 dev 단계에서 등록 방식을 따로 외울 필요가 없습니다.

## 10. 운영 반영 시 등록이 완성되는 방식

현재 권장 경로는 `promote` 스크립트를 통한 반영입니다.

```bash
python -m devtools.scripts.promote sample_flow
```

이 스크립트는 아래 작업을 자동으로 수행합니다.

- dev 워크플로 패키지를 `api/workflows/`로 복사합니다.
- 대응하는 dev MCP 모듈을 `api/mcp/`로 복사합니다.
- `devtools.mcp.` import를 `api.mcp.`로 치환합니다.
- import 검증을 수행합니다.
- 성공하면 dev 원본을 삭제합니다.

즉, 현재 설정에서는 등록 작업의 마지막 단계가 단순 이동이 아니라 `복사 + import 치환 + 검증`까지 포함된 과정입니다.

## 11. 새 워크플로를 등록할 때 실무 체크리스트

- `api/workflows/<workflow_id>/`가 패키지 형태인지 확인합니다.
- `__init__.py`에 `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`이 있는지 확인합니다.
- `build_lg_graph`가 실제 callable인지 확인합니다.
- `workflow_id`가 중복되지 않는지 확인합니다.
- `handoff_keywords`가 필요한 업무인지 먼저 판단합니다.
- 도구가 필요하면 등록 함수가 그래프 빌드 경로에서 호출되는지 확인합니다.
- dev에서 검증한 뒤 `promote`로 반영하는지 확인합니다.

## 12. 자주 발생하는 등록 실패 원인

### 레지스트리에서 아예 안 보이는 경우

- 디렉터리가 패키지가 아니어서 발견되지 않는 경우가 있습니다.
- `get_workflow_definition()`이 없어서 건너뛰는 경우가 있습니다.
- `build_lg_graph`가 callable이 아니어서 예외가 나는 경우가 있습니다.

### `start_chat`에서 분기되지 않는 경우

- `handoff_keywords`를 비워 둔 경우가 있습니다.
- 사용자 발화와 키워드가 실제로 겹치지 않는 경우가 있습니다.
- 키워드가 지나치게 일반적이어서 다른 흐름과 충돌하는 경우가 있습니다.

### 도구 호출에서 실패하는 경우

- MCP 등록 함수는 만들었지만 호출하지 않은 경우가 있습니다.
- dev MCP import가 운영 경로로 올 때 정리되지 않은 경우가 있습니다.
- `tool_id`와 핸들러 등록 이름이 맞지 않는 경우가 있습니다.

## 13. 팀에 공유할 때 기억하면 좋은 문장

현재 저장소에서 워크플로 등록은 중앙 파일 수정 작업이 아니라, `패키지 계약을 맞춘 뒤 자동 발견 구조에 태운다`는 개념으로 이해하는 편이 가장 정확합니다.

즉, 등록을 잘하려면 수동 목록을 찾기보다 `__init__.py 계약`, `handoff_keywords`, `MCP 등록 호출 위치` 세 가지를 먼저 확인하는 편이 좋습니다.
