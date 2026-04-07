# 1. 진행 사항
- `api/file_delivery/router.py`, `api/file_delivery/file_delivery_service.py`, `api/file_delivery/__init__.py`를 확인해 파일 전달 계층의 엔드포인트, 저장 구조, 메타데이터 백엔드, 이미지 variant 생성 흐름을 정리했다.
- `api/llm/registry.py`, `api/llm/service.py`, `api/llm/prompt/system.py`를 확인해 LLM 인스턴스 생성 방식, 메시지 조립 순서, 시스템 프롬프트/시간대/사용자 프로필 주입 방식을 정리했다.
- `api/mcp/models.py`, `api/mcp/registry.py`, `api/mcp/client.py`, `api/mcp/executor.py`, `api/mcp/tool_adapter.py`, `api/mcp/tool_selector.py`, `api/mcp/local_tools.py`, `api/mcp/cache.py`, `api/mcp/errors.py`를 확인해 MCP 도구 등록-선택-실행 파이프라인을 정리했다.
- `api/workflows/registry.py`, `api/workflows/lg_orchestrator.py`, `api/workflows/langgraph_checkpoint.py`, `api/workflows/lg_state.py`, `api/workflows/state_service.py`, `api/workflows/models.py`와 `start_chat`, `translator`, `travel_planner`, `chart_maker` 하위 워크플로 파일을 확인해 LangGraph 기반 오케스트레이션 구조와 서브그래프 데이터 흐름을 정리했다.
- 상위 연계 확인을 위해 `api/cube/router.py`, `api/cube/service.py`, `api/cube/worker.py`도 함께 확인했고, 전체 파이프라인은 `Cube 수신 -> 큐 적재 -> worker 처리 -> workflows -> llm/mcp 호출 -> Cube 응답`으로 연결됨을 확인했다.
- 조사 시 사용한 대표 명령은 `find api/... -maxdepth 2 -type f | sort`, `sed -n '1,260p' ...`, `rg -n "WORKFLOW_DEFINITION|get_workflow_definition|handoff_keywords|tool_tags" api/workflows/...`였다.
- 폴더별 구조와 데이터 파이프라인 요약:
  - `api/file_delivery`: `router.py`가 `/file-delivery`, `/api/v1/file-delivery/upload`, `/file-delivery/files/<file_id>` 계열 엔드포인트를 받고, `file_delivery_service.py`가 `save_uploaded_file()` -> `save_file_bytes()` -> 원본 저장(`FILE_DELIVERY_STORAGE_DIR/original/<user>/<date>/...`) -> 메타데이터 저장(Redis 또는 in-memory) -> `file_url` 반환 순으로 처리한다. 조회 시 `get_file_variant()`가 파일 메타데이터를 읽고, 이미지면 Pillow 기반 `_create_variant_bytes()`로 resize/thumbnail variant를 `variant/<file_id>/...`에 생성한 뒤 `send_file()`로 응답한다.
  - `api/llm`: `service.generate_reply()`가 호출 진입점이며 `_build_messages()`에서 `history`와 현재 사용자 입력을 LangChain 메시지로 조립하고, `prompt/system.py`의 `get_system_prompt()`가 기본 시스템 프롬프트 + 한국 시간대 정보 + 사용자 프로필 문맥을 합성한다. 이후 `_get_llm()` 또는 `registry.get_llm()`가 `config.LLM_BASE_URL`, `config.LLM_MODEL`, `config.LLM_API_KEY` 기반 `ChatOpenAI`를 만들고 `invoke()` 결과를 `_extract_content()`로 문자열 응답으로 정리한다.
  - `api/mcp`: `models.py`가 `MCPServerConfig`, `MCPTool`, `MCPToolCall`, `MCPToolResult`를 정의하고, `registry.py`가 서버/도구 메타데이터를 메모리 레지스트리에 등록한다. 워크플로가 `MCPToolCall`을 만들면 `executor.execute_tool_call()`이 먼저 `local_tools.get_handler()`로 로컬 핸들러를 찾고, 없으면 `get_tool()`/`get_server()`로 원격 서버 정보를 조회해 `MCPClient.execute()`로 폴백한다. `tool_selector.select_tools()`는 workflow의 `tool_tags`와 도구 태그를 교집합 기준으로 필터링하고, `cache.py`는 MCP 메타데이터 JSON 캐시를 `MCP_CACHE_DIR`에 저장한다.
  - `api/workflows`: `registry.load_workflows()`가 `api.workflows.*` 하위 패키지를 동적 탐색해 `get_workflow_definition()`을 수집하고, 각 workflow의 `entry_node_id`, `state_cls`, `handoff_keywords`, `tool_tags`를 정규화한다. 실제 런타임 진입점은 `lg_orchestrator.handle_message()`이며, 여기서 `build_thread_id(user_id, channel_id)`로 LangGraph thread를 만들고 `get_checkpointer()`로 MongoDBSaver 또는 MemorySaver를 연결한 뒤 루트 `start_chat` 그래프를 invoke/resume 한다. `start_chat/lg_graph.py`는 `entry`에서 프로필을 1회 적재하고 `classify`에서 `handoff_keywords` 기반으로 `translator`/`chart_maker`/`travel_planner` 서브그래프로 분기하거나, 기본 경로로 `retrieve_context -> plan_response -> generate_reply`를 거쳐 `api.llm.service.generate_reply()`를 호출한다. `translator/lg_graph.py`는 interrupt/resume으로 원문/목표 언어를 보완한 뒤 `api.mcp.executor.execute_tool_call()`로 `translate` 도구를 실행하고, `travel_planner/lg_graph.py`는 목적지/스타일/일정을 단계별로 수집해 추천 일정을 만든다. `chart_maker/lg_graph.py`는 현재 차트 유형 수집과 스펙 뼈대를 만드는 스켈레톤 단계까지 구현되어 있다.

# 2. 수정 내용
- 새 저널 파일 `doc/journals/260407/260407_182345-api-structure-pipeline-review.md`를 생성했다.
- 코드 로직 수정은 없었고, 이번 작업은 `api/file_delivery`, `api/llm`, `api/mcp`, `api/workflows` 및 연계 확인용 `api/cube` 구조/데이터 파이프라인 문서화에 한정했다.

# 3. 다음 단계
- 사용자가 원하면 이번 저널의 내용을 바탕으로 `doc/project_structure_api.md` 또는 별도 아키텍처 문서에 폴더별 데이터 파이프라인 섹션을 본문 형태로 승격해 반영한다.
- 사용자가 원하면 `api/archive`, `api/scheduled_tasks`, `api/profile`까지 같은 형식으로 이어서 구조/파이프라인 문서를 확장한다.
- 사용자 확인 필요: 이번 정리를 저널로만 유지할지, 상시 참조용 문서(`doc/*.md`)에도 반영할지 범위를 결정한다.

# 4. 메모리 업데이트
- 변경 없음
