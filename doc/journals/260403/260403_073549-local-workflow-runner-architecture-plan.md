## 1. 진행 사항

- 사용자와 함께 Cube 없이 로컬에서 workflow를 개발하는 구조를 재정의했다.
- 기존 구조를 확인하기 위해 `api/workflows/orchestrator.py`, `api/workflows/state_service.py`, `api/conversation_service.py`, `api/cube/service.py`, `api/workflows/registry.py`, `api/__init__.py`를 검토했다.
- 확인한 핵심 사항은 다음과 같다.
  - 현재 workflow resume은 `api/workflows/orchestrator.py`에서 `user_id` 기준 상태 로딩/저장으로 동작한다.
  - 현재 대화 이력 저장은 `api/cube/service.py`와 `api/conversation_service.py` 쪽에 묶여 있어, Cube를 통하지 않으면 production 대화 저장 로직과 자연스럽게 분리할 수 있다.
  - workflow 패키지 로딩은 `api/workflows/registry.py`의 `discover_workflows(package_name=...)` 구조를 활용하면 다른 패키지 루트도 로드할 수 있다.
- 로컬 개발용 아키텍처 방향을 아래처럼 정리했다.

```text
devtools/
  workflow_runner/
    app.py
    routes.py
    templates/
    static/
  workflows/
    <workflow_id>/
      __init__.py
      graph.py
      nodes.py
      state.py
      routing.py
      prompts.py

api/
  workflows/
    <workflow_id>/    # promotion 이후 운영 반영 경로
```

- 사용자 요구를 반영해 local dev mode의 원칙도 정리했다.
  - production conversation history와 공유하지 않는다.
  - 각 개발자는 자기 브라우저의 local storage 기준으로 transcript를 관리한다.
  - 사용자는 로컬 transcript를 직접 삭제(reset)할 수 있어야 한다.
  - transcript와 trace는 `.json` 또는 `.txt`로 export/download 할 수 있어야 한다.
  - localhost 페이지에서 workflow reply, 상태 JSON, trace text를 쉽게 모니터링할 수 있어야 한다.
- `devtools/workflows/<workflow_id>`를 `api/workflows/<workflow_id>`와 같은 구조로 두는 방안이 팀의 작업 방식에는 더 적합하다고 결론냈다.
- 다만 운영 반영 단계는 "copy and paste"가 아니라 promotion(move) 개념으로 관리하는 것이 맞다고 정리했다.
- promotion의 의미도 문서화했다.
  - 개발 중: `devtools/workflows/<workflow_id>`
  - 운영 반영 준비 완료: 검토 후 `api/workflows/<workflow_id>`로 이동
  - 이후 registry/test/deploy 순서로 검증

## 2. 수정 내용

- `MEMORY.md`
  - 로컬 workflow 개발 규칙을 추가했다.
  - `devtools/workflow_runner/`, `devtools/workflows/<workflow_id>/`, production과 분리된 local transcript, promotion(move 기준) 원칙을 기록했다.
- 새 저널 파일을 생성했다.
  - `doc/journals/260403/260403_073549-local-workflow-runner-architecture-plan.md`
- 코드 변경은 없고, 아키텍처/개발 계획 문서화만 수행했다.
- 이번 세션에서 정리한 구현 방향은 다음과 같다.
  - `devtools/workflow_runner/`는 localhost 개발 UI와 export/reset/trace 기능을 담당한다.
  - `devtools/workflows/`는 초안 workflow 작성 공간이다.
  - `api/workflows/`는 promotion 이후 운영 반영 경로다.
  - local dev transcript/history는 브라우저 저장소 기준으로 production과 분리한다.
  - 서버 쪽은 workflow 실행 결과와 상태 JSON만 반환하도록 단순화하는 방향이 적절하다.

## 3. 다음 단계

- `devtools/workflow_runner/` 기본 골격을 만든다.
  - `app.py`, `routes.py`, `templates/`, `static/`
- `devtools/workflows/__init__.py`와 샘플 workflow 하나를 만든다.
- dev runner에서 `discover_workflows(package_name=\"devtools.workflows\")`를 사용해 로컬 workflow를 로드하도록 구현한다.
- localhost 페이지에 아래 기능을 넣는다.
  - 메시지 입력
  - reply 확인
  - workflow state JSON 보기
  - trace text 보기
  - transcript reset
  - transcript `.json` / `.txt` export
- promotion 절차를 스크립트나 문서로 만든다.
  - 예: `scripts/promote_workflow.py`
  - 역할: `devtools/workflows/<workflow_id>`를 `api/workflows/<workflow_id>`로 이동하고 기본 검증 명령을 안내
- 팀 가이드 문서에 "로컬 workflow 작성 -> runner에서 검증 -> promotion -> 테스트 -> 배포" 흐름을 추가한다.

## 4. 메모리 업데이트

- `MEMORY.md`에 로컬 workflow 개발 규칙을 추가했다.
