"""dev runner 전용 대화 이력 저장소.

api/conversation_service.py를 mirror하지 않고, dev runner가 필요로 하는 최소 API
(``append_message``, ``get_history``)만 파일 기반 JSONL 저장소로 제공한다.

api 측과의 차이:
- MongoDB / 메모리 backend 분기 없음 (항상 파일 저장).
- 메시지 ID 기반 중복 방지 없음 (dev runner는 사용자 입력 / 봇 응답을 1:1로 추가).
- TimedRotatingFileHandler 같은 회전 정책 없음.
- prod ``api.config`` 의존 없음 — 저장 경로는 본 모듈이 단독 결정.

저장 구조: ``devtools/var/conversation_history/<user_id>/<conversation_id>.jsonl``.
api 측 ``_LocalFileBackend``가 이전에 같은 경로에 만들어 둔 dev 이력과 호환되도록
같은 디렉터리/파일 형태(JSONL: 한 줄당 메시지 한 건)를 사용한다.
"""

import json
from pathlib import Path
from typing import Any

_DEV_VAR_ROOT = Path(__file__).resolve().parent.parent / "var"
_HISTORY_DIR = _DEV_VAR_ROOT / "conversation_history"

_DEFAULT_CONVERSATION_ID = "default"


def _ensure_dir() -> Path:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_DIR


def _conversation_path(user_id: str, conversation_id: str | None) -> Path:
    user_dir = _HISTORY_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / f"{conversation_id or _DEFAULT_CONVERSATION_ID}.jsonl"


def append_message(
    user_id: str,
    message: dict[str, Any],
    *,
    conversation_id: str | None = None,
) -> None:
    """대화 이력에 메시지 한 건을 JSONL 한 줄로 append한다."""

    _ensure_dir()
    path = _conversation_path(user_id, conversation_id)
    line = json.dumps(dict(message), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def get_history(
    user_id: str,
    *,
    conversation_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """저장된 대화 이력을 반환한다."""

    if conversation_id is not None:
        return _read_one(user_id, conversation_id, limit=limit)

    return _read_all_for_user(user_id, limit=limit)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    messages: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    messages.append(obj)
    except OSError:
        return []
    return messages


def _read_one(user_id: str, conversation_id: str, *, limit: int | None) -> list[dict[str, Any]]:
    path = _conversation_path(user_id, conversation_id)
    messages = _read_jsonl(path)
    return messages[-limit:] if limit is not None else messages


def _read_all_for_user(user_id: str, *, limit: int | None) -> list[dict[str, Any]]:
    user_dir = _HISTORY_DIR / user_id
    if not user_dir.exists():
        return []
    merged: list[dict[str, Any]] = []
    for path in sorted(user_dir.glob("*.jsonl")):
        merged.extend(_read_jsonl(path))
    return merged[-limit:] if limit is not None else merged
