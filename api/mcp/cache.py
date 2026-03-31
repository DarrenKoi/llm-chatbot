"""MCP 도구 메타데이터 캐시 스텁을 제공한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path("var") / "mcp_cache"


def load_cache(cache_key: str) -> dict[str, Any] | None:
    """캐시된 JSON 문서를 조회한다."""

    cache_path = CACHE_DIR / f"{cache_key}.json"
    if not cache_path.exists():
        return None
    return json.loads(cache_path.read_text(encoding="utf-8"))


def save_cache(cache_key: str, payload: dict[str, Any]) -> Path:
    """JSON 문서를 캐시에 저장한다."""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{cache_key}.json"
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache_path
