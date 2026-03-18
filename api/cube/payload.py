"""Cube 메시지 페이로드 파싱 유틸리티."""


def extract_user_id(payload: object) -> str | None:
    """페이로드에서 사용자 ID를 추출한다.

    Cube의 richnotificationmessage 구조와 일반 웹 요청의
    평탄한 구조를 모두 지원한다.
    """
    if not isinstance(payload, dict):
        return None

    user_id = payload.get("user_id") or payload.get("user")
    if user_id:
        return str(user_id)

    rich_message = payload.get("richnotificationmessage")
    if not isinstance(rich_message, dict):
        return None

    header = rich_message.get("header")
    if not isinstance(header, dict):
        return None

    sender = header.get("from")
    if not isinstance(sender, dict):
        return None

    nested_user_id = sender.get("uniquename")
    if not nested_user_id:
        return None
    return str(nested_user_id)
