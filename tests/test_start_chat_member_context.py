"""member_lookup 결과가 generate_reply_node 컨텍스트에 포함되는지 검증."""

from api.cube.intents import ReplyIntent, TextIntent
from api.workflows.start_chat.lg_graph import generate_reply_node


def test_member_context_flows_into_reply_prompt(mocker):
    captured = {}

    def _fake_generate_reply_intent(*, history, user_message, **kwargs):
        captured["user_message"] = user_message
        return ReplyIntent(blocks=[TextIntent(text="확인했습니다.")])

    mocker.patch("api.llm.service.generate_reply_intent", side_effect=_fake_generate_reply_intent)
    mocker.patch("api.conversation_service.get_history", return_value=[])
    mocker.patch("api.file_delivery.list_files_for_user", return_value=[])

    member_block = "[사내 구성원 정보]\n- 홍길동 | 개발팀 | 백엔드 엔지니어 | 담당: 인증 시스템"
    state = {
        "user_id": "u1",
        "channel_id": "c1",
        "user_message": "누가 인증 담당이야?",
        "retrieved_contexts": [member_block],
    }

    result = generate_reply_node(state)

    # 컨텍스트가 augmented user_message에 포함되어 LLM에 전달된다
    assert member_block in captured["user_message"]
    assert "누가 인증 담당이야?" in captured["user_message"]
    assert result["messages"][-1].content == "확인했습니다."
