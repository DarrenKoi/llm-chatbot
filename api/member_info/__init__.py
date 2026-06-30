"""사내 구성원 디렉터리(member_info) REST 연동 패키지.

별도 서비스 oss-mcp-fastapi의 `/skewnono/member_info/v1` 엔드포인트를 HTTP로 호출한다.
OpenSearch 설정은 해당 FastAPI 서비스가 소유하며, 챗봇은 REST만 호출한다.
"""

from api.member_info.client import (
    filter_members,
    lookup_member,
    normalize_record,
    search_members,
)

__all__ = [
    "filter_members",
    "lookup_member",
    "normalize_record",
    "search_members",
]
