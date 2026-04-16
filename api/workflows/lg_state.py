"""LangGraph 워크플로에서 사용하는 공유 기본 상태 정의.

워크플로별 전용 상태는 각 워크플로 패키지 안의 lg_state.py에 정의한다.
예: api/workflows/translator/lg_state.py → TranslatorState
"""

from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class ChatState(TypedDict, total=False):
    """모든 LangGraph 워크플로가 공유하는 기본 상태."""

    messages: Annotated[list, add_messages]
    user_id: str
    channel_id: str
    user_message: str
    conversation_ended: bool
    pending_reply: str
