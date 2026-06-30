"""member_lookup_node 테스트 — 트리거 감지·포맷·무동작 폴백."""

import pytest

from api import config
from api.workflows.start_chat.member_lookup import node
from api.workflows.start_chat.member_lookup.llm_decision import MemberLookupDecision
from api.workflows.start_chat.member_lookup.prompts import MEMBER_CONTEXT_HEADER


@pytest.fixture()
def _enabled(monkeypatch):
    monkeypatch.setattr(config, "MEMBER_INFO_ENABLED", True)
    monkeypatch.setattr(config, "MEMBER_INFO_BASE_URL", "http://mi.example.com/v1")
    monkeypatch.setattr(config, "MEMBER_INFO_INCLUDE_CONTACT", True)


_MEMBER = {
    "NAME_KOR": "홍길동",
    "DEPT_NAME_KOR": "개발팀",
    "PART_NAME_KO": "플랫폼파트",
    "JOB_NAME_KOR": "백엔드 엔지니어",
    "RESP_CONT": "인증 시스템",
    "OFFICE_TEL_NO": "031-000-0000",
    "MOBILE_TEL_NO": "010-1234-5678",
}


def test_disabled_is_noop(monkeypatch, mocker):
    monkeypatch.setattr(config, "MEMBER_INFO_ENABLED", False)
    monkeypatch.setattr(config, "MEMBER_INFO_BASE_URL", "http://mi.example.com/v1")
    decide = mocker.patch("api.workflows.start_chat.member_lookup.node.decide_member_lookup")

    assert node.member_lookup_node({"user_message": "누가 인증 담당이야?"}) == {}
    decide.assert_not_called()


def test_command_override_forces_search(_enabled, mocker):
    decide = mocker.patch("api.workflows.start_chat.member_lookup.node.decide_member_lookup")
    search = mocker.patch(
        "api.workflows.start_chat.member_lookup.node.search_members",
        return_value=[_MEMBER],
    )

    result = node.member_lookup_node({"user_message": "!담당 인증 시스템"})

    decide.assert_not_called()  # 명령어 경로는 LLM 호출 없음
    search.assert_called_once_with("인증 시스템")
    block = result["retrieved_contexts"][-1]
    assert block.startswith(MEMBER_CONTEXT_HEADER)
    assert "홍길동" in block
    assert "담당: 인증 시스템" in block
    assert "☎ 031-000-0000 / 010-1234-5678" in block


def test_keyword_gate_blocks_non_person_query(_enabled, mocker):
    decide = mocker.patch("api.workflows.start_chat.member_lookup.node.decide_member_lookup")

    assert node.member_lookup_node({"user_message": "오늘 날씨 어때?"}) == {}
    decide.assert_not_called()


def test_auto_detect_runs_llm_and_searches(_enabled, mocker):
    mocker.patch(
        "api.workflows.start_chat.member_lookup.node.decide_member_lookup",
        return_value=MemberLookupDecision(needs_lookup=True, mode="search", query="인증"),
    )
    search = mocker.patch(
        "api.workflows.start_chat.member_lookup.node.search_members",
        return_value=[_MEMBER],
    )

    result = node.member_lookup_node({"user_message": "누가 인증 담당이야?"})

    search.assert_called_once_with("인증")
    assert MEMBER_CONTEXT_HEADER in result["retrieved_contexts"][-1]


def test_auto_detect_filter_mode_uses_filter(_enabled, mocker):
    mocker.patch(
        "api.workflows.start_chat.member_lookup.node.decide_member_lookup",
        return_value=MemberLookupDecision(needs_lookup=True, mode="filter", query="", filters={"dept": "개발팀"}),
    )
    flt = mocker.patch(
        "api.workflows.start_chat.member_lookup.node.filter_members",
        return_value=[_MEMBER],
    )

    node.member_lookup_node({"user_message": "개발팀 부서에 누구 있어?"})

    flt.assert_called_once_with(dept="개발팀")


def test_no_members_is_noop(_enabled, mocker):
    mocker.patch(
        "api.workflows.start_chat.member_lookup.node.decide_member_lookup",
        return_value=MemberLookupDecision(needs_lookup=True, mode="search", query="없는사람"),
    )
    mocker.patch("api.workflows.start_chat.member_lookup.node.search_members", return_value=[])

    assert node.member_lookup_node({"user_message": "누가 없는사람 담당이야?"}) == {}


def test_contact_toggle_off_hides_phone(_enabled, monkeypatch, mocker):
    monkeypatch.setattr(config, "MEMBER_INFO_INCLUDE_CONTACT", False)
    mocker.patch("api.workflows.start_chat.member_lookup.node.search_members", return_value=[_MEMBER])

    result = node.member_lookup_node({"user_message": "!담당 인증"})

    block = result["retrieved_contexts"][-1]
    assert "☎" not in block
    assert "010-1234-5678" not in block


def test_appends_to_existing_contexts(_enabled, mocker):
    mocker.patch("api.workflows.start_chat.member_lookup.node.search_members", return_value=[_MEMBER])

    result = node.member_lookup_node({"user_message": "!담당 인증", "retrieved_contexts": ["기존 RAG 컨텍스트"]})

    assert result["retrieved_contexts"][0] == "기존 RAG 컨텍스트"
    assert MEMBER_CONTEXT_HEADER in result["retrieved_contexts"][1]


def test_lookup_exception_degrades_to_noop(_enabled, mocker):
    mocker.patch(
        "api.workflows.start_chat.member_lookup.node.search_members",
        side_effect=RuntimeError("boom"),
    )

    assert node.member_lookup_node({"user_message": "!담당 인증"}) == {}
