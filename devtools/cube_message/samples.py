"""검증된 richnotification 샘플 모음.

프로젝트 루트의 ``richnotification_samples.md``에 있는 JSON 샘플을 로드해
Cube에 그대로 전송한다. 블록 빌더(``blocks.py``)를 거치지 않으므로
페이로드 구조가 문서와 1:1로 대응된다.

샘플 목록은 ``list_samples()``로 확인하고, 직접 보낼 때는 ``send_sample(N, ...)``
한 줄로 끝낸다. 새 샘플이 마크다운에 추가되면 자동으로 인식된다.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from devtools.cube_message.client import CubeMessageConfig, send_raw_content

_SAMPLES_PATH = Path(__file__).resolve().parents[2] / "richnotification_samples.md"
_SAMPLE_PATTERN = re.compile(
    r"## Sample (?P<num>\d+):\s*(?P<title>.+?)\n.*?```json\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def list_samples() -> dict[int, str]:
    """샘플 번호 → 제목 매핑."""

    text = _samples_text()
    return {int(m.group("num")): m.group("title").strip() for m in _SAMPLE_PATTERN.finditer(text)}


def load_sample_content(number: int) -> list[dict[str, Any]]:
    """N번 샘플의 ``richnotification.content`` 배열을 dict로 반환."""

    text = _samples_text()
    for match in _SAMPLE_PATTERN.finditer(text):
        if int(match.group("num")) == number:
            payload = json.loads(match.group("body"))
            content = payload["richnotification"]["content"]
            if not isinstance(content, list):
                raise ValueError(f"Sample {number}의 content 형식이 올바르지 않습니다.")
            return content
    raise ValueError(f"Sample {number}을(를) 찾을 수 없습니다.")


def send_sample(
    number: int,
    *,
    user_id: str,
    channel_id: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """N번 샘플을 그대로 Cube에 전송."""

    return send_raw_content(
        load_sample_content(number),
        user_id=user_id,
        channel_id=channel_id,
        config=config,
    )


@lru_cache(maxsize=1)
def _samples_text() -> str:
    return _SAMPLES_PATH.read_text(encoding="utf-8")
