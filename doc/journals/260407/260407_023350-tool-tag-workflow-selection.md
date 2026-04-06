## 1. 진행 사항
- `doc/journals/260406/260406-mcp-tool-scaling-research.md`를 기준으로 Phase 1 방향인 workflow 기반 `tool_tags` 적용 방안을 코드에 반영했다.
- `api/mcp/models.py`에 `MCPTool.tags` 정규화 로직을 추가해 도구 태그를 소문자 tuple로 관리하도록 변경했다.
- `api/workflows/registry.py`에 `WorkflowDefinition.tool_tags` 정규화와 workflow 등록 로그 기록 항목을 추가했다.
- `api/mcp/tool_selector.py`의 스텁 `select_tools()`를 실제 태그 필터링 로직으로 교체했다.
- `api/workflows/translator/__init__.py`, `api/workflows/translator/tools.py`에 번역 workflow용 `tool_tags`/`tags`를 붙여 첫 적용 사례를 만들었다.
- `pytest tests/test_mcp_tool_selector.py tests/test_workflow_registry.py tests/test_translator_workflow.py -v`와 `pytest tests/ -v`를 실행해 회귀 여부를 확인했다.
- 변경 사항을 `git add -A`, `git commit -m "mcp: 워크플로 도구 태그 선택 로직 추가"`, `git push origin main`으로 반영했다.

## 2. 수정 내용
- 수정 파일: `api/mcp/models.py`
  - `MCPTool.tags` 필드와 `_normalize_tags()`를 추가했다.
- 수정 파일: `api/workflows/registry.py`
  - workflow 정의의 `tool_tags`를 정규화하고 `workflow_registered` 로그에 포함하도록 변경했다.
- 수정 파일: `api/mcp/tool_selector.py`
  - workflow의 `tool_tags`와 `MCPTool.tags`를 비교해 도구 후보를 좁히는 로직을 구현했다.
- 수정 파일: `api/workflows/translator/__init__.py`
  - translator workflow 정의에 `tool_tags=("translation", "language")`를 추가했다.
- 수정 파일: `api/workflows/translator/tools.py`
  - `translate` 도구에 `tags=("translation", "language")`를 추가했다.
- 수정 파일: `tests/test_mcp_tool_selector.py`
  - workflow 태그 필터링, 태그 미설정 fallback, 태그 정규화 테스트를 신규 추가했다.
- 수정 파일: `tests/test_workflow_registry.py`
  - `tool_tags` 정규화와 workflow 로그 payload 검증을 추가했다.
- 수정 파일: `tests/test_translator_workflow.py`
  - translator MCP 도구가 태그와 함께 등록되는지 확인하는 테스트를 추가했다.
- 수정 파일: `MEMORY.md`
  - MCP 도구 선택 규칙 섹션을 추가했다.

## 3. 다음 단계
- `api/mcp/tool_selector.select_tools()`를 실제 LLM tool binding 또는 MCP 실행 경로에 연결해 태그 필터링이 런타임에서도 사용되도록 반영한다.
- 다른 workflow와 MCP 도구에도 `tool_tags`/`tags`를 부여해 태그 체계를 확장한다.
- 필요하면 workflow 단위에서 한 단계 더 나아가 node 단위 도구 바인딩 구조를 설계한다.

## 4. 메모리 업데이트
- `MEMORY.md`에 `MCP 도구 선택 규칙` 섹션을 추가했다.
