"""devtools 워크플로 예제의 회귀 동작을 검증한다."""

from devtools.workflows.translator_example.graph import build_graph as build_translator_graph
from devtools.workflows.translator_example.nodes import collect_source_text_node as translator_collect_source_text_node
from devtools.workflows.translator_example.nodes import (
    collect_target_language_node as translator_collect_target_language_node,
)
from devtools.workflows.translator_example.state import TranslatorExampleState
from devtools.workflows.travel_planner_example.graph import build_graph as build_travel_graph
from devtools.workflows.travel_planner_example.nodes import build_plan_node as travel_build_plan_node
from devtools.workflows.travel_planner_example.nodes import collect_preference_node as travel_collect_preference_node
from devtools.workflows.travel_planner_example.state import TravelPlannerExampleState


def test_translator_example_accepts_full_answer_while_waiting_for_source():
    """문장과 언어를 한 번에 다시 보내면 곧바로 번역 단계로 넘어간다."""

    state = TranslatorExampleState(
        user_id="dev-user",
        workflow_id="translator_example",
        node_id="collect_source_text",
        status="waiting_user_input",
    )

    result = translator_collect_source_text_node(state, '"감사합니다"를 영어로 번역해줘')

    assert result.action == "resume"
    assert result.next_node_id == "translate"
    assert result.data_updates["source_text"] == "감사합니다"
    assert result.data_updates["target_language"] == "en"


def test_translator_example_stop_message_completes_cleanly():
    """stop 의도가 들어오면 예제 워크플로도 종료 응답을 반환한다."""

    state = TranslatorExampleState(
        user_id="dev-user",
        workflow_id="translator_example",
        node_id="collect_target_language",
        status="waiting_user_input",
        source_text="안녕하세요",
        last_asked_slot="target_language",
    )

    result = translator_collect_target_language_node(state, "취소")

    assert result.action == "complete"
    assert result.next_node_id == "entry"
    assert result.reply == "번역은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."
    assert result.data_updates["source_text"] == ""


def test_travel_planner_example_complete_resets_to_entry():
    """완료 후 다음 턴이 새 요청으로 시작되도록 entry로 되돌린다."""

    state = TravelPlannerExampleState(
        user_id="dev-user",
        workflow_id="travel_planner_example",
        node_id="build_plan",
        destination="오사카",
        travel_style="먹거리",
        duration_text="2박 3일",
        companion_type="친구",
    )

    result = travel_build_plan_node(state, "ignored")

    assert result.action == "complete"
    assert result.next_node_id == "entry"


def test_travel_planner_example_stop_message_completes_cleanly():
    """여행 계획 예제도 stop 의도를 종료로 처리한다."""

    state = TravelPlannerExampleState(
        user_id="dev-user",
        workflow_id="travel_planner_example",
        node_id="collect_preference",
        status="waiting_user_input",
        last_asked_slot="travel_style",
    )

    result = travel_collect_preference_node(state, "bye")

    assert result.action == "complete"
    assert result.next_node_id == "entry"
    assert result.reply == "여행 계획은 여기서 마칠게요. 다른 요청이 있으면 편하게 말씀해주세요."
    assert result.data_updates["travel_style"] == ""


def test_devtools_graphs_expose_done_edges():
    """예제 그래프가 종료 지점을 시각적으로 드러낸다."""

    translator_edges = build_translator_graph()["edges"]
    travel_edges = build_travel_graph()["edges"]

    assert ("translate", "done", "번역 완료") in translator_edges
    assert ("build_plan", "done", "계획 완료") in travel_edges
