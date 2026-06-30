"""member_info FastAPI REST 클라이언트.

세 엔드포인트를 감싼다:
- GET /member/{emp_no}  → 사번 정확 조회 (lookup_member)
- GET /search           → 자유 검색 (search_members)
- GET /filter           → 패싯 필터 (filter_members)

설계 원칙: 비활성/미설정/오류 상황에서 절대 예외를 올리지 않고 빈 결과(None/[])를
반환한다. 그래야 member_info 서비스가 없는 집·테스트 환경이나 운영 중 서비스 장애에도
챗봇이 평소대로(컨텍스트 없이) 동작한다(graceful degrade).
"""

import logging

import httpx

from api import config

log = logging.getLogger(__name__)

# normalize_record가 반환하는 구조화 키 ← member_info 원본 필드
_RECORD_FIELD_MAP = (
    ("emp_no", "EMP_NO"),
    ("name", "NAME_KOR"),
    ("dept", "DEPT_NAME_KOR"),
    ("part", "PART_NAME_KO"),
    ("job", "JOB_NAME_KOR"),
    ("responsibility", "RESP_CONT"),
    ("campus", "CENTRIC"),
    ("work_place", "PLACE_OF_WORK"),
    ("work_group", "WGRP_NAM"),
    ("office_tel", "OFFICE_TEL_NO"),
    ("mobile_tel", "MOBILE_TEL_NO"),
)


def _is_configured() -> bool:
    return bool(config.MEMBER_INFO_ENABLED and config.MEMBER_INFO_BASE_URL)


def _request(path: str, params: dict[str, object]) -> dict | None:
    """member_info REST를 호출하고 JSON dict를 반환한다(실패 시 None)."""

    if not _is_configured():
        return None

    url = f"{config.MEMBER_INFO_BASE_URL}{path}"
    cleaned = {key: value for key, value in params.items() if value not in (None, "")}

    try:
        response = httpx.get(url, params=cleaned, timeout=config.MEMBER_INFO_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        log.warning("member_info_request_failed path=%s error=%s", path, exc)
        return None

    if not isinstance(payload, dict):
        log.warning("member_info_response_invalid path=%s type=%s", path, type(payload).__name__)
        return None
    return payload


def _coerce_size(size: int | None, default: int) -> int:
    if size is None:
        return default
    return max(1, min(int(size), 50))


def lookup_member(emp_no: str) -> dict | None:
    """사번(EMP_NO)으로 구성원 1명을 정확 조회한다. 없으면 None."""

    normalized = (emp_no or "").strip()
    if not normalized:
        return None

    payload = _request(f"/member/{normalized}", {})
    if not payload or not payload.get("found"):
        return None

    member = payload.get("member")
    return member if isinstance(member, dict) else None


def search_members(
    query: str,
    *,
    match_all: bool = True,
    phrase: bool = False,
    size: int | None = None,
) -> list[dict]:
    """통합 검색(이름/부서/직무/담당 업무)으로 구성원 목록을 조회한다."""

    text = (query or "").strip()
    if not text:
        return []

    payload = _request(
        "/search",
        {
            "q": text,
            "match_all": str(match_all).lower(),
            "phrase": str(phrase).lower(),
            "size": _coerce_size(size, config.MEMBER_INFO_RESULT_LIMIT),
        },
    )
    return _extract_members(payload)


def filter_members(
    *,
    text: str | None = None,
    dept: str | None = None,
    part: str | None = None,
    campus: str | None = None,
    work_place: str | None = None,
    work_group: str | None = None,
    level: str | None = None,
    match_all: bool = True,
    phrase: bool = False,
    size: int | None = None,
) -> list[dict]:
    """패싯(부서/팀/캠퍼스 등) 필터로 구성원 목록을 조회한다."""

    if not any([text, dept, part, campus, work_place, work_group, level]):
        return []

    payload = _request(
        "/filter",
        {
            "text": text,
            "dept": dept,
            "part": part,
            "campus": campus,
            "work_place": work_place,
            "work_group": work_group,
            "level": level,
            "match_all": str(match_all).lower(),
            "phrase": str(phrase).lower(),
            "size": _coerce_size(size, config.MEMBER_INFO_RESULT_LIMIT),
        },
    )
    return _extract_members(payload)


def _extract_members(payload: dict | None) -> list[dict]:
    if not payload:
        return []
    members = payload.get("members")
    if not isinstance(members, list):
        return []
    return [member for member in members if isinstance(member, dict)]


def normalize_record(member: dict) -> dict:
    """member_info 원본 레코드를 구조화 dict로 변환한다(값 없는 키는 제외).

    프로필 provider와 컨텍스트 포맷터가 공유하는 중간 표현이다.
    """

    record: dict[str, str] = {}
    for key, source_field in _RECORD_FIELD_MAP:
        value = member.get(source_field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            record[key] = text
    return record
