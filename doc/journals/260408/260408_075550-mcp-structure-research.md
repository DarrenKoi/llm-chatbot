# MCP 구조 리서치 정리

## 1. 진행 사항
- 저장소의 실제 구조를 기준으로 MCP 배치가 적절한지 검토했다. 확인 대상은 `api/mcp/`, `api/workflows/`, `devtools/mcp/`, `doc/guideline/workflow_추가_가이드.md`였다.
- `rg --files`, `find api -maxdepth 3 -type d | sort`, `rg -n "api/mcp|mcp" doc api devtools tests README.md` 명령으로 MCP 관련 파일과 문서 연결 지점을 확인했다.
- `api/mcp/executor.py`, `api/mcp/registry.py`, `api/mcp/tool_selector.py`, `api/workflows/registry.py`, `api/workflows/translator/tools.py`를 읽고 현재 MCP가 공용 런타임 인프라인지, 워크플로 전용 구현인지 구분했다.
- MCP 공식 문서의 host-client-server 아키텍처와 tools 노출 방식을 확인해, 현재 저장소 구조와 일반적인 MCP 관리 방식을 비교했다.
- 결론으로 `api/mcp/` 자체는 상위 인프라 계층에 두는 편이 맞고, 워크플로 의존 정책은 `api/mcp/`가 아니라 워크플로/오케스트레이션 계층으로 옮기는 것이 더 자연스럽다는 판단을 정리했다.

## 2. 수정 내용
- 신규 파일 생성: `doc/journals/260408/260408_075550-mcp-structure-research.md`
- 코드 수정은 없었다.
- 리서치 결과 요약:
  - `api/mcp/executor.py`, `api/mcp/registry.py`, `api/mcp/client.py`, `api/mcp/local_tools.py`는 공용 MCP 런타임 인프라 역할을 하고 있어 `api/workflows/` 아래로 내릴 성격이 아니다.
  - `api/workflows/translator/tools.py`와 `doc/guideline/workflow_추가_가이드.md` 기준으로는, 워크플로별 도구 등록/바인딩은 각 workflow 패키지 근처에 두는 방식이 이미 정착되어 있다.
  - 현재 `api/mcp/tool_selector.py`가 `api.workflows.registry.get_workflow()`를 직접 참조하고 있어 MCP 계층이 workflow 정책을 아는 구조다. 이 부분이 현재 구조에서 가장 어색한 결합 지점이다.
  - 권장 방향은 `api/mcp/`는 유지하고, workflow 기반 도구 선택 정책은 `api/workflows/` 또는 별도 오케스트레이션 계층으로 이동하는 것이다.

## 3. 다음 단계
- `api/mcp/tool_selector.py`의 책임을 재검토해 workflow 정책 코드를 `api/workflows/` 또는 `api/orchestration/` 계층으로 이동할지 결정한다.
- MCP 서버/클라이언트/레지스트리가 더 늘어날 경우 `api/mcp/servers/` 또는 `api/mcp/runtime/` 같은 하위 구조를 도입할지 검토한다.
- 새 workflow를 추가할 때는 현재 가이드대로 `api/workflows/<workflow_id>/tools.py`에서 workflow 전용 도구 등록을 유지하고, 공용 MCP 인프라와 혼합하지 않도록 기준을 문서화한다.

## 4. 메모리 업데이트
- 변경 없음
