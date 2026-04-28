"""LangGraph 워크플로에서 사용하는 dev 측 공유 기본 상태 정의 (mirror of api/workflows/lg_state.py).

이 파일은 ``api/workflows/lg_state.py``의 mirror 사본이다. ``HARNESS.md``의
"api/ ↔ devtools/ 격리 정책"에 따라 두 파일을 같은 PR에서 함께 업데이트해야 한다.

api 측과의 차이:
- ``reply_intents`` 타입을 ``list[Any]``로 두어 ``api.cube.intents.BlockIntent`` 의존을 끊었다.
  ``BlockIntent`` 자체도 mirror 대상이지만(``shared_docs/workflow_catalog.md`` §3.5의 후속 단계),
  현재 단계에서는 dev 워크플로가 이 필드를 직접 사용하지 않으므로 ``Any``로 충분하다.

워크플로별 전용 상태는 각 워크플로 패키지 안의 lg_state.py에 정의한다.
예: devtools/workflows/travel_planner_example/lg_state.py → TravelPlannerExampleState
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class ChatState(TypedDict, total=False):
    """모든 LangGraph 워크플로가 공유하는 기본 상태."""

    messages: Annotated[list, add_messages]
    user_id: str
    channel_id: str
    user_message: str
    conversation_ended: bool
    pending_reply: str
    reply_intents: list[Any] | None
