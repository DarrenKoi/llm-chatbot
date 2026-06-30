"""member_info REST 클라이언트 테스트 (httpx mock)."""

import httpx
import pytest

from api import config
from api.member_info import client


@pytest.fixture()
def _enabled(monkeypatch):
    monkeypatch.setattr(config, "MEMBER_INFO_ENABLED", True)
    monkeypatch.setattr(config, "MEMBER_INFO_BASE_URL", "http://mi.example.com/v1")
    monkeypatch.setattr(config, "MEMBER_INFO_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(config, "MEMBER_INFO_RESULT_LIMIT", 5)


def _response(url, payload):
    return httpx.Response(200, json=payload, request=httpx.Request("GET", url))


def test_lookup_member_returns_record_when_found(mocker, _enabled):
    get_mock = mocker.patch(
        "api.member_info.client.httpx.get",
        return_value=_response(
            "http://mi.example.com/v1/member/12345",
            {"found": True, "member": {"EMP_NO": "12345", "NAME_KOR": "홍길동"}},
        ),
    )

    member = client.lookup_member("12345")

    assert member == {"EMP_NO": "12345", "NAME_KOR": "홍길동"}
    args, kwargs = get_mock.call_args
    assert args[0] == "http://mi.example.com/v1/member/12345"
    assert kwargs["timeout"] == 2.0


def test_lookup_member_returns_none_when_not_found(mocker, _enabled):
    mocker.patch(
        "api.member_info.client.httpx.get",
        return_value=_response("http://mi.example.com/v1/member/0", {"found": False, "member": None}),
    )

    assert client.lookup_member("0") is None


def test_search_members_parses_member_list(mocker, _enabled):
    get_mock = mocker.patch(
        "api.member_info.client.httpx.get",
        return_value=_response(
            "http://mi.example.com/v1/search",
            {"count": 2, "members": [{"NAME_KOR": "A"}, {"NAME_KOR": "B"}, "garbage"]},
        ),
    )

    members = client.search_members("출하 검사")

    assert members == [{"NAME_KOR": "A"}, {"NAME_KOR": "B"}]
    _, kwargs = get_mock.call_args
    assert kwargs["params"]["q"] == "출하 검사"
    assert kwargs["params"]["size"] == 5


def test_filter_members_drops_empty_params(mocker, _enabled):
    get_mock = mocker.patch(
        "api.member_info.client.httpx.get",
        return_value=_response("http://mi.example.com/v1/filter", {"count": 0, "members": []}),
    )

    client.filter_members(dept="개발팀", part=None, text="")

    _, kwargs = get_mock.call_args
    params = kwargs["params"]
    assert params["dept"] == "개발팀"
    assert "part" not in params
    assert "text" not in params


def test_filter_members_without_any_filter_skips_request(mocker, _enabled):
    get_mock = mocker.patch("api.member_info.client.httpx.get")

    assert client.filter_members() == []
    get_mock.assert_not_called()


def test_disabled_returns_empty_without_calling_http(mocker, monkeypatch):
    monkeypatch.setattr(config, "MEMBER_INFO_ENABLED", False)
    monkeypatch.setattr(config, "MEMBER_INFO_BASE_URL", "http://mi.example.com/v1")
    get_mock = mocker.patch("api.member_info.client.httpx.get")

    assert client.lookup_member("12345") is None
    assert client.search_members("홍길동") == []
    get_mock.assert_not_called()


def test_http_error_degrades_to_empty(mocker, _enabled):
    mocker.patch(
        "api.member_info.client.httpx.get",
        side_effect=httpx.ConnectTimeout("nope", request=httpx.Request("GET", "http://mi.example.com/v1/search")),
    )

    assert client.search_members("홍길동") == []
    assert client.lookup_member("12345") is None


def test_normalize_record_maps_and_drops_blank_fields():
    record = client.normalize_record(
        {
            "EMP_NO": "12345",
            "NAME_KOR": "홍길동",
            "DEPT_NAME_KOR": "개발팀",
            "PART_NAME_KO": "플랫폼파트",
            "JOB_NAME_KOR": "백엔드 엔지니어",
            "RESP_CONT": "인증 시스템",
            "OFFICE_TEL_NO": "",
            "MOBILE_TEL_NO": None,
        }
    )

    assert record == {
        "emp_no": "12345",
        "name": "홍길동",
        "dept": "개발팀",
        "part": "플랫폼파트",
        "job": "백엔드 엔지니어",
        "responsibility": "인증 시스템",
    }
