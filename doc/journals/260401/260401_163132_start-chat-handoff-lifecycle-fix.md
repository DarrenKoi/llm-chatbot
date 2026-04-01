## 1. 진행 사항
- `api/workflows/orchestrator.py`에서 `start_chat` 완료 상태 재시작, handoff 상태 변환, 자식 워크플로 종료 후 부모 복귀 로직을 정리했다.
- `api/workflows/state_service.py`에서 workflow별 상태 클래스를 기준으로 저장 payload를 직렬화하고, `data`에만 남아 있던 필드를 다시 상태 객체로 복원하도록 보강했다.
- `api/workflows/registry.py`에 각 workflow의 `state_cls`를 등록해서 오케스트레이터와 상태 복원 로직이 대상 워크플로 전용 상태를 알 수 있게 했다.
- `tests/test_start_chat_workflow.py`에 follow-up turn 재시작, handoff 후 chart workflow 진행, 자식 workflow 종료 후 `start_chat` 복귀에 대한 회귀 테스트를 추가했다.
- 검증 명령으로 `uv run pytest tests/test_start_chat_workflow.py -v`와 `uv run pytest tests/ -v`를 실행했고 전체 96개 테스트가 통과했다.

## 2. 수정 내용
- 가능한 이슈 1: 완료된 `start_chat` 세션이 `generate_reply`에서 그대로 저장되어 다음 메시지에서 `entry/classify/retrieve_context/plan_response`를 건너뛰고 stale 상태를 재사용할 수 있었다.
  해결: `handle_message()`에서 저장된 상태를 workflow 전용 상태로 정규화한 뒤, `workflow_id == "start_chat"` 이고 `status == "completed"`이면 `entry`부터 다시 시작하는 새 상태로 재초기화했다.
- 가능한 이슈 2: handoff 시 현재 상태 객체를 그대로 재사용해서 `chart_type`, `outline`, `recipe_type` 같은 workflow 전용 필드가 없는 상태로 자식 그래프를 타게 되어 `AttributeError` 또는 잘못된 기본값 사용이 발생할 수 있었다.
  해결: `build_state()`와 `_coerce_state()`를 추가해 workflow 전환 시 대상 `state_cls` 기준으로 상태 payload를 재구성했다. 또한 `_apply_result()`가 `data_updates`를 `state.data`뿐 아니라 실제 상태 필드에도 반영하도록 바꿨다.
- 가능한 이슈 3: handoff된 자식 workflow가 `action="reply"`로 끝나면 스택이 남아서 다음 사용자 입력이 `done` 노드 또는 자식 workflow에 묶일 수 있었다.
  해결: `run_graph()`에서 마지막 `NodeResult`를 기준으로 terminal `reply` 또는 `complete`를 감지하고, 스택이 남아 있으면 부모 workflow로 복귀시키도록 수정했다. 부모가 `start_chat`이면 다음 턴을 위해 `entry` 상태로 초기화한다.
- 변경 파일:
  `api/workflows/orchestrator.py`
  `api/workflows/state_service.py`
  `api/workflows/registry.py`
  `tests/test_start_chat_workflow.py`
  `doc/journals/260401/260401_163132_start-chat-handoff-lifecycle-fix.md`

## 3. 다음 단계
- `ppt_maker`, `recipe_requests`, `at_wafer_quota`에도 handoff 이후 다중 턴 종료 복귀 시나리오를 같은 방식으로 회귀 테스트에 추가하면 안전하다.
- 현재 부모 복귀는 `start_chat` 기준으로 다음 턴 재시작에 맞춰 정리되어 있으므로, 향후 부모 workflow가 늘어나면 스택에 parent snapshot 전체를 저장할지 검토가 필요하다.
- `api/workflows/ppt_maker/routing.py`의 `state.template_path` 참조처럼 상태 정의와 맞지 않는 필드 사용이 더 없는지 workflow 패키지 전반을 한 번 점검하는 것이 좋다.

## 4. 메모리 업데이트
- 변경 없음
