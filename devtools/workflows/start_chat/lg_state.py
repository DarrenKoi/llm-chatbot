"""dev start_chat 전용 상태 정의.

운영 StartChatState(api/workflows/start_chat/lg_state.py)와 의도적으로 다르다.
- profile_*, retrieved_contexts: dev에서 의미 없으므로 미포함.
- handoff_match_reason: classify가 어떤 키워드로 매칭됐는지 기록 — trace/state 가시화용.
"""

from devtools.workflows.lg_state import ChatState


class DevStartChatState(ChatState, total=False):
    """dev runner start_chat 그래프의 상태."""

    active_workflow: str
    handoff_match_reason: str
