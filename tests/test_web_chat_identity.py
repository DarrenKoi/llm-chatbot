"""LASTUSER cookie 기반 신원 도출을 검증한다."""

from unittest.mock import patch

import pytest
from werkzeug.exceptions import Unauthorized

from api import config
from api.web_chat.identity import get_current_web_chat_user


def test_returns_user_when_lastuser_cookie_present(app):
    with app.test_request_context("/", headers={"Cookie": "LASTUSER=alice; LASTUSERNAME=Alice Kim"}):
        user = get_current_web_chat_user()

    assert user.user_id == "alice"
    assert user.user_name == "Alice Kim"


def test_falls_back_to_user_id_when_username_cookie_missing(app):
    with app.test_request_context("/", headers={"Cookie": "LASTUSER=alice"}):
        user = get_current_web_chat_user()

    assert user.user_id == "alice"
    assert user.user_name == "alice"


@patch.object(config, "WEB_CHAT_DEV_USER", "")
def test_raises_unauthorized_when_cookie_missing(app):
    with app.test_request_context("/"):
        with pytest.raises(Unauthorized):
            get_current_web_chat_user()


@patch.object(config, "WEB_CHAT_DEV_USER", "")
def test_raises_unauthorized_when_cookie_blank(app):
    with app.test_request_context("/", headers={"Cookie": "LASTUSER=  "}):
        with pytest.raises(Unauthorized):
            get_current_web_chat_user()


@patch.object(config, "WEB_CHAT_DEV_USER", "devuser")
@patch.object(config, "WEB_CHAT_DEV_USER_NAME", "Dev User")
def test_dev_user_fallback_used_when_localhost_and_cookie_missing(app):
    with app.test_request_context("/", base_url="http://localhost:5000"):
        user = get_current_web_chat_user()

    assert user.user_id == "devuser"
    assert user.user_name == "Dev User"


@patch.object(config, "WEB_CHAT_DEV_USER", "devuser")
@patch.object(config, "WEB_CHAT_DEV_USER_NAME", "")
def test_dev_user_name_falls_back_to_user_id(app):
    with app.test_request_context("/", base_url="http://127.0.0.1:5000"):
        user = get_current_web_chat_user()

    assert user.user_id == "devuser"
    assert user.user_name == "devuser"


@patch.object(config, "WEB_CHAT_DEV_USER", "devuser")
def test_real_cookie_takes_precedence_over_dev_fallback(app):
    with app.test_request_context(
        "/",
        base_url="http://localhost:5000",
        headers={"Cookie": "LASTUSER=alice; LASTUSERNAME=Alice Kim"},
    ):
        user = get_current_web_chat_user()

    assert user.user_id == "alice"
    assert user.user_name == "Alice Kim"


@patch.object(config, "WEB_CHAT_DEV_USER", "devuser")
def test_dev_user_fallback_rejected_for_non_localhost_host(app):
    with app.test_request_context("/", base_url="http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com"):
        with pytest.raises(Unauthorized):
            get_current_web_chat_user()


@patch.object(config, "WEB_CHAT_DEV_USER", "")
def test_dev_user_fallback_disabled_when_env_unset(app):
    with app.test_request_context("/", base_url="http://localhost:5000"):
        with pytest.raises(Unauthorized):
            get_current_web_chat_user()
