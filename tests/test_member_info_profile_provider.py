"""member_info 기반 프로필 provider 테스트."""

from api.profile.member_info_provider import load_profile_from_member_info
from api.profile.models import UserProfile
from api.profile.service import _coerce_profile


def test_provider_maps_member_record_to_profile_dict(mocker):
    mocker.patch(
        "api.profile.member_info_provider.lookup_member",
        return_value={
            "EMP_NO": "12345",
            "NAME_KOR": "홍길동",
            "DEPT_NAME_KOR": "개발팀",
            "PART_NAME_KO": "플랫폼파트",
            "JOB_NAME_KOR": "백엔드 엔지니어",
            "RESP_CONT": "인증 시스템",
            "PLACE_OF_WORK": "이천",
        },
    )

    profile = load_profile_from_member_info("12345")

    assert profile == {
        "name": "홍길동",
        "organization": "개발팀",
        "team": "플랫폼파트",
        "role": "백엔드 엔지니어",
        "work_location": "이천",
        "responsibility": "인증 시스템",
        "source": "member_info",
    }


def test_provider_falls_back_to_campus_for_work_location(mocker):
    mocker.patch(
        "api.profile.member_info_provider.lookup_member",
        return_value={"NAME_KOR": "홍길동", "CENTRIC": "청주"},
    )

    profile = load_profile_from_member_info("12345")

    assert profile["work_location"] == "청주"


def test_provider_returns_none_when_not_found(mocker):
    mocker.patch("api.profile.member_info_provider.lookup_member", return_value=None)

    assert load_profile_from_member_info("12345") is None


def test_provider_returns_none_for_blank_user_id(mocker):
    lookup = mocker.patch("api.profile.member_info_provider.lookup_member")

    assert load_profile_from_member_info("  ") is None
    lookup.assert_not_called()


def test_provider_output_coerces_into_user_profile_with_responsibility():
    """provider dict가 프로필 정규화를 거쳐 담당 업무까지 채우는지 확인."""

    payload = {
        "name": "홍길동",
        "organization": "개발팀",
        "team": "플랫폼파트",
        "role": "백엔드 엔지니어",
        "work_location": "이천",
        "responsibility": "인증 시스템",
        "source": "member_info",
    }

    profile = _coerce_profile(payload, user_id="12345", default_source="member_info")

    assert profile == UserProfile(
        user_id="12345",
        name="홍길동",
        team="플랫폼파트",
        organization="개발팀",
        work_location="이천",
        role="백엔드 엔지니어",
        responsibility="인증 시스템",
        source="member_info",
    )
    assert "- 담당 업무: 인증 시스템" in profile.to_prompt_text()
