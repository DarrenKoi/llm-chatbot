"""LASTUSER cookie에서 현재 웹 채팅 사용자를 도출한다."""

from flask import request
from werkzeug.exceptions import Unauthorized

from api import config
from api.web_chat.models import WebChatUser

_LOCALHOST_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})


def get_current_web_chat_user() -> WebChatUser:
    """LASTUSER cookie를 읽어 WebChatUser를 반환한다.

    cookie가 없거나 빈 문자열이면 401 Unauthorized를 발생시킨다.
    브라우저가 보낸 body의 user_id는 절대 신뢰하지 않는다.

    개발 편의를 위해 ``WEB_CHAT_DEV_USER``가 설정되어 있고 요청이 localhost에서 왔을 때에 한해
    cookie 없이도 해당 dev 사용자로 동작한다. 운영 환경에서는 ``WEB_CHAT_DEV_USER``를 비워둔다.
    """
    user_id = request.cookies.get("LASTUSER", "").strip()
    if user_id:
        user_name = request.cookies.get("LASTUSERNAME", "").strip() or user_id
        return WebChatUser(user_id=user_id, user_name=user_name)

    dev_user = _localhost_dev_user()
    if dev_user is not None:
        return dev_user

    raise Unauthorized("LASTUSER cookie is required.")


def _localhost_dev_user() -> WebChatUser | None:
    if not config.WEB_CHAT_DEV_USER:
        return None
    if not _is_localhost_request():
        return None
    return WebChatUser(
        user_id=config.WEB_CHAT_DEV_USER,
        user_name=config.WEB_CHAT_DEV_USER_NAME or config.WEB_CHAT_DEV_USER,
    )


def _is_localhost_request() -> bool:
    host = (request.host or "").split(":")[0].strip().lower()
    return host in _LOCALHOST_HOSTS
