"""Dev runner 사용자 식별자 유틸리티."""

import os
import re
import socket

_SAFE_PC_ID_PATTERN = re.compile(r"[^a-z0-9]+")


def get_default_dev_user_id() -> str:
    """로컬 개발용 기본 user_id를 반환한다."""

    raw_pc_id = (
        os.environ.get("DEV_RUNNER_PC_ID")
        or os.environ.get("COMPUTERNAME")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
    )
    pc_id = _normalize_pc_id(raw_pc_id)
    return f"dev_{pc_id}"


def _normalize_pc_id(raw_pc_id: str) -> str:
    normalized = _SAFE_PC_ID_PATTERN.sub("_", raw_pc_id.strip().lower()).strip("_")
    return normalized or "local"
