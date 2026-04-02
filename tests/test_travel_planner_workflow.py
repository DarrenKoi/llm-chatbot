"""travel_planner 샘플 워크플로 테스트."""

from api.workflows.orchestrator import run_graph
from api.workflows.travel_planner.graph import build_graph
from api.workflows.travel_planner.state import TravelPlannerState


def _make_state(*, node_id: str = "entry") -> TravelPlannerState:
    return TravelPlannerState(
        user_id="travel_user",
        workflow_id="travel_planner",
        node_id=node_id,
        data={},
    )


def test_travel_planner_asks_style_for_generic_request():
    """목적지와 취향이 없으면 먼저 여행 스타일을 묻는다."""

    state = _make_state()

    reply = run_graph(build_graph(), state, "여행 계획 짜줘")

    assert "어떤 스타일의 여행" in reply
    assert state.status == "waiting_user_input"
    assert state.node_id == "collect_preference"
    assert state.last_asked_slot == "travel_style"


def test_travel_planner_recommends_destinations_after_style_answer():
    """스타일만 있으면 목적지 후보를 추천하고 선택을 기다린다."""

    state = _make_state(node_id="collect_preference")

    reply = run_graph(build_graph(), state, "휴양 여행으로 추천해줘")

    assert "제주" in reply
    assert "방콕" in reply
    assert state.status == "waiting_user_input"
    assert state.node_id == "collect_destination"
    assert state.suggested_destinations == ["제주", "방콕", "싱가포르"]


def test_travel_planner_builds_plan_when_destination_and_duration_are_available():
    """목적지와 일정이 있으면 바로 기본 여행 계획을 제안한다."""

    state = _make_state()

    reply = run_graph(build_graph(), state, "도쿄 3박 4일 여행 계획 짜줘")

    assert "도쿄 3박 4일 여행" in reply
    assert "시부야" in reply
    assert "아사쿠사" in reply
    assert state.status == "completed"
    assert state.destination == "도쿄"
    assert state.duration_text == "3박 4일"


def test_travel_planner_supports_multi_turn_recommendation_flow():
    """스타일 추천 후 목적지를 고르면 다음 턴에서 계획을 완성한다."""

    state = _make_state()

    first_reply = run_graph(build_graph(), state, "trip plan")
    assert state.node_id == "collect_preference"
    assert state.status == "waiting_user_input"
    assert "도시" in first_reply

    second_reply = run_graph(build_graph(), state, "먹거리 위주로 가고 싶어")
    assert state.node_id == "collect_destination"
    assert state.status == "waiting_user_input"
    assert "오사카" in second_reply

    final_reply = run_graph(build_graph(), state, "오사카 2박 3일 친구와 갈래")
    assert "오사카 2박 3일 여행" in final_reply
    assert "도톤보리" in final_reply
    assert state.status == "completed"
    assert state.companion_type == "친구"
