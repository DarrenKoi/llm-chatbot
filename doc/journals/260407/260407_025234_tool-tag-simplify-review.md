## 1. 진행 사항
- 이전 세션(`260407_023350-tool-tag-workflow-selection.md`)에서 구현한 MCP 도구 태그 선택 로직에 대해 코드 리뷰를 수행했다.
- `/simplify`(3개 병렬 리뷰 에이전트: 코드 재사용, 코드 품질, 효율성)와 Codex 리뷰를 동시에 실행해 4방향 검증을 진행했다.
- 리뷰에서 발견된 이슈 4건을 수정하고 전체 테스트(139개)를 통과시켰다.

## 2. 수정 내용

### 수정 파일: `api/mcp/models.py`
- `_normalize_tags()` → `normalize_tags()`로 공개 함수로 변경했다.
- `context` 키워드 인자를 추가해 에러 메시지에 맥락 정보를 포함할 수 있도록 했다.
- `(bytes, bytearray)` 타입을 명시적으로 거부하는 가드를 추가했다.
- 태그 요소가 `str`이 아닌 경우 `TypeError`를 발생시키는 검증을 추가했다 (기존에는 `str(tag)`로 무음 변환).

### 수정 파일: `api/workflows/registry.py`
- 중복된 `_normalize_tags()` 함수(19줄)를 삭제했다.
- `from api.mcp.models import normalize_tags`로 공유 함수를 임포트하도록 변경했다.
- `_normalize_workflow_definition()`에서 `normalize_tags(context=module_name)`으로 호출을 교체했다.

### 수정 파일: `api/workflows/translator/__init__.py`
- `TRANSLATOR_TOOL_TAGS` 상수를 모듈 수준에 정의했다.
- `get_workflow_definition()`에서 리터럴 대신 상수를 참조하도록 변경했다.

### 수정 파일: `api/workflows/translator/tools.py`
- `from api.workflows.translator import TRANSLATOR_TOOL_TAGS`를 추가했다.
- `register_translator_tools()`에서 태그 리터럴 대신 `TRANSLATOR_TOOL_TAGS` 상수를 참조하도록 변경했다.

### 수정 파일: `api/mcp/tool_selector.py`
- `_matches_required_tags()` 헬퍼 함수를 제거했다.
- `required_tags`를 `frozenset`으로 변환한 뒤 `isdisjoint()`로 OR 매칭을 수행하도록 변경했다.

## 3. 다음 단계
- `select_tools()`를 실제 LLM tool binding 또는 MCP 실행 경로에 연결해 태그 필터링이 런타임에서도 사용되도록 반영한다.
- 다른 workflow와 MCP 도구에도 `tool_tags`/`tags`를 부여해 태그 체계를 확장한다.
- Codex 리뷰에서 발견된 스테일 캐시 이슈(`load_workflows()`가 다른 `package_name`으로 재호출 시 첫 캐시를 반환)는 이번 diff 범위 밖이므로 별도 세션에서 검토한다.

## 4. 메모리 업데이트
- 변경 없음
