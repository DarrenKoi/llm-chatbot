"""member_info 기반 사용자 프로필 provider.

Cube `uniquename`(= user_id) == 사번(EMP_NO) 이므로, 정확 조회로 질문자 정보를 가져와
`USER_PROFILE_PROVIDER_CALLABLE` 훅을 통해 `[사용자 프로필]` 시스템 프롬프트 블록을 채운다.

설정 예:
    USER_PROFILE_PROVIDER_CALLABLE=api.profile.member_info_provider:load_profile_from_member_info
"""

import logging

from api.member_info import lookup_member, normalize_record

log = logging.getLogger(__name__)


def load_profile_from_member_info(user_id: str) -> dict | None:
    """사번(user_id)으로 구성원을 조회해 프로필 dict를 반환한다(없으면 None).

    반환 dict는 `api.profile.service._normalize_profile`가 이해하는 키를 사용한다.
    None을 반환하면 기존 로더 체인(api/redis)이 다음 후보로 폴백한다.
    """

    emp_no = (user_id or "").strip()
    if not emp_no:
        return None

    member = lookup_member(emp_no)
    if not member:
        return None

    record = normalize_record(member)

    profile = {
        "name": record.get("name", ""),
        "organization": record.get("dept", ""),
        "team": record.get("part", ""),
        "role": record.get("job", ""),
        "work_location": record.get("work_place") or record.get("campus", ""),
        "responsibility": record.get("responsibility", ""),
        "source": "member_info",
    }

    if not any(value for key, value in profile.items() if key != "source"):
        return None

    return profile
