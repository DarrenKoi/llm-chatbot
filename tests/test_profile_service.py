import pytest
import httpx

from api.profile.models import UserProfile
from api.profile.service import load_user_profile


@pytest.fixture(autouse=True)
def _reset_redis_singleton(monkeypatch):
    """테스트 간 Redis 싱글턴을 초기화한다."""
    monkeypatch.setattr("api.profile.service._redis_client", None)


class _FakeRedisClient:
    def __init__(self, payload):
        self._payload = payload
        self.last_key = ""

    def hgetall(self, key):
        self.last_key = key
        return self._payload


def test_load_user_profile_uses_custom_provider(monkeypatch):
    monkeypatch.setattr("api.config.USER_PROFILE_PROVIDER_CALLABLE", "custom.profile:load_profile")
    monkeypatch.setattr(
        "api.profile.service._resolve_provider",
        lambda _path: lambda _user_id: UserProfile(
            user_id="u1",
            name="홍길동",
            source="custom_company",
        ),
    )

    profile = load_user_profile("u1")

    assert profile == UserProfile(user_id="u1", name="홍길동", source="custom_company")


def test_load_user_profile_uses_profile_api_before_redis(mocker, monkeypatch):
    monkeypatch.setattr("api.config.USER_PROFILE_PROVIDER_CALLABLE", "")
    monkeypatch.setattr("api.config.USER_PROFILE_API_URL", "https://profile.example.com/users/{user_id}")
    monkeypatch.setattr("api.config.USER_PROFILE_API_TIMEOUT_SECONDS", 1.5)
    monkeypatch.setattr("api.config.USER_PROFILE_REDIS_URL", "redis://profile")

    get_mock = mocker.patch(
        "api.profile.service.httpx.get",
        return_value=httpx.Response(
            200,
            json={"name": "홍길동", "team_name": "Platform Engineering"},
            request=httpx.Request("GET", "https://profile.example.com/users/u1"),
        ),
    )
    redis_mock = mocker.patch("api.profile.service.redis.from_url")

    profile = load_user_profile("u1")

    assert profile == UserProfile(
        user_id="u1",
        name="홍길동",
        team="Platform Engineering",
        source="profile_api",
    )
    get_mock.assert_called_once_with("https://profile.example.com/users/u1", timeout=1.5)
    redis_mock.assert_not_called()


def test_load_user_profile_falls_back_to_redis_on_api_timeout(mocker, monkeypatch):
    monkeypatch.setattr("api.config.USER_PROFILE_PROVIDER_CALLABLE", "")
    monkeypatch.setattr("api.config.USER_PROFILE_API_URL", "https://profile.example.com/users/{user_id}")
    monkeypatch.setattr("api.config.USER_PROFILE_REDIS_URL", "redis://profile")
    monkeypatch.setattr("api.config.USER_PROFILE_REDIS_KEY_PREFIX", "user:profile")

    mocker.patch(
        "api.profile.service.httpx.get",
        side_effect=httpx.ConnectTimeout(
            "timed out",
            request=httpx.Request("GET", "https://profile.example.com/users/u1"),
        ),
    )
    fake_redis = _FakeRedisClient({
        b"name": b"\xed\x99\x8d\xea\xb8\xb8\xeb\x8f\x99",
        b"site": b"\xec\x9d\xb4\xec\xb2\x9c",
    })
    from_url_mock = mocker.patch("api.profile.service.redis.from_url", return_value=fake_redis)

    profile = load_user_profile("u1")

    assert profile == UserProfile(
        user_id="u1",
        name="홍길동",
        work_location="이천",
        source="redis",
    )
    from_url_mock.assert_called_once_with(
        "redis://profile",
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=False,
    )
    assert fake_redis.last_key == "user:profile:u1"
