"""LLM 응답을 콘텐츠 유형별로 분리하고 Cube 전송 방법을 결정하는 모듈.

일반 텍스트 → multimessage (40줄 청킹)
코드 블록/표 → richnotification (청킹 불필요)
"""

import re
from dataclasses import dataclass
from typing import Literal

from api import config

_CODE_FENCE_RE = re.compile(r"^(`{3,})\s*(\S*)")
_TABLE_SEP_RE = re.compile(r"^\|[\s:-]+\|")
_TABLE_ROW_RE = re.compile(r"^\|.+\|$")
_HEADER_RE = re.compile(r"^#{1,6}\s")


@dataclass
class DeliveryItem:
    method: Literal["multi", "rich"]
    content: str
    kind: Literal["text", "code", "table"] = "text"


def chunk_text(text: str, *, max_lines: int = 0) -> list[str]:
    """텍스트를 multimessage 전송용 청크로 분할한다.

    `plan_delivery`와 달리 코드/표 감지나 rich 라우팅을 수행하지 않는다.
    이미 multimessage로 보내기로 결정된 텍스트(예: TextIntent)에 사용한다.
    """
    if max_lines <= 0:
        max_lines = config.CUBE_MESSAGE_MAX_LINES

    if not text or not text.strip():
        return []

    return _chunk_text(text, max_lines)


def plan_delivery(text: str, *, max_lines: int = 0) -> list[DeliveryItem]:
    """LLM 응답 텍스트를 DeliveryItem 리스트로 변환한다.

    Args:
        text: LLM 응답 전체 텍스트
        max_lines: multimessage 청크당 최대 줄 수 (0이면 config 값 사용)

    Returns:
        순서대로 전송할 DeliveryItem 리스트
    """
    if max_lines <= 0:
        max_lines = config.CUBE_MESSAGE_MAX_LINES

    if not text or not text.strip():
        return [DeliveryItem(method="multi", content="")]

    # 짧은 메시지는 파싱 없이 바로 반환
    if text.count("\n") + 1 <= max_lines and not config.CUBE_RICH_ROUTING_ENABLED:
        return [DeliveryItem(method="multi", content=text)]

    blocks = _parse_blocks(text)
    if not blocks:
        return [DeliveryItem(method="multi", content="")]

    use_rich = config.CUBE_RICH_ROUTING_ENABLED

    items: list[DeliveryItem] = []
    for block in blocks:
        if use_rich and block.kind in ("code", "table"):
            items.append(DeliveryItem(method="rich", content=block.content, kind=block.kind))
        else:
            for chunk in _chunk_text(block.content, max_lines):
                items.append(DeliveryItem(method="multi", content=chunk, kind=block.kind))

    return _merge_adjacent(items, max_lines)


# ---------------------------------------------------------------------------
# Internal types and helpers
# ---------------------------------------------------------------------------


@dataclass
class _Block:
    kind: Literal["text", "code", "table"]
    content: str


def _parse_blocks(text: str) -> list[_Block]:
    """텍스트를 코드 펜스 / 표 / 일반 텍스트 블록으로 분리한다."""
    blocks: list[_Block] = []
    lines = text.split("\n")
    buf: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        fence_match = _CODE_FENCE_RE.match(line)
        if fence_match:
            # 먼저 쌓인 텍스트 버퍼를 플러시
            if buf:
                blocks.extend(_split_text_and_tables(buf))
                buf = []

            fence_marker = fence_match.group(1)
            fence_len = len(fence_marker)
            code_lines = [line]
            i += 1
            # 닫는 펜스 찾기
            while i < len(lines):
                code_lines.append(lines[i])
                if re.match(rf"^`{{{fence_len},}}\s*$", lines[i]):
                    i += 1
                    break
                i += 1
            blocks.append(_Block(kind="code", content="\n".join(code_lines)))
            continue

        buf.append(line)
        i += 1

    # 남은 버퍼 플러시
    if buf:
        blocks.extend(_split_text_and_tables(buf))

    # 빈 블록 제거
    return [b for b in blocks if b.content.strip()]


def _split_text_and_tables(lines: list[str]) -> list[_Block]:
    """텍스트 줄 목록에서 표 블록을 분리한다."""
    blocks: list[_Block] = []
    buf: list[str] = []
    i = 0

    while i < len(lines):
        # 표 감지: 구분자 행 (`|---|...---|`)이 있으면 위아래로 표 범위 탐색
        if _TABLE_SEP_RE.match(lines[i]):
            if buf and _TABLE_ROW_RE.match(buf[-1]):
                table_start_line = buf.pop()
                # 버퍼에 남은 텍스트를 먼저 플러시
                if buf:
                    blocks.append(_Block(kind="text", content="\n".join(buf)))
                    buf = []
                table_lines = [table_start_line, lines[i]]
            else:
                if buf:
                    blocks.append(_Block(kind="text", content="\n".join(buf)))
                    buf = []
                table_lines = [lines[i]]

            i += 1
            # 표 본문 행 수집
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                table_lines.append(lines[i])
                i += 1

            blocks.append(_Block(kind="table", content="\n".join(table_lines)))
            continue

        buf.append(lines[i])
        i += 1

    if buf:
        blocks.append(_Block(kind="text", content="\n".join(buf)))

    return blocks


def _chunk_text(text: str, max_lines: int) -> list[str]:
    """일반 텍스트를 max_lines 이하의 청크로 분할한다.

    분할 우선순위: 빈 줄(문단 경계) > 마크다운 헤더 > 줄 경계
    """
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return [text]

    # 문단 단위로 분리 (빈 줄 기준)
    paragraphs = _split_paragraphs(lines)

    chunks: list[str] = []
    current_lines: list[str] = []
    current_count = 0

    for para in paragraphs:
        para_line_count = para.count("\n") + 1

        # 단일 문단이 max_lines 초과 → 줄 단위 분할
        if para_line_count > max_lines:
            # 먼저 현재 버퍼 플러시
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_count = 0

            para_lines = para.split("\n")
            for j in range(0, len(para_lines), max_lines):
                chunks.append("\n".join(para_lines[j : j + max_lines]))
            continue

        # 추가하면 초과 → 현재 버퍼 플러시
        separator_line_count = 1 if current_lines else 0
        if current_count + separator_line_count + para_line_count > max_lines:
            if current_lines:
                chunks.append("\n".join(current_lines))
            current_lines = para.split("\n")
            current_count = para_line_count
        else:
            if current_lines:
                current_lines.append("")  # 문단 사이 빈 줄
                current_count += 1
            current_lines.extend(para.split("\n"))
            current_count += para_line_count

    if current_lines:
        chunks.append("\n".join(current_lines))

    return [c for c in chunks if c.strip()]


def _split_paragraphs(lines: list[str]) -> list[str]:
    """줄 목록을 빈 줄 기준으로 문단으로 분리한다."""
    paragraphs: list[str] = []
    buf: list[str] = []

    for line in lines:
        if line.strip() == "":
            if buf:
                paragraphs.append("\n".join(buf))
                buf = []
        else:
            # 마크다운 헤더에서도 분할
            if _HEADER_RE.match(line) and buf:
                paragraphs.append("\n".join(buf))
                buf = []
            buf.append(line)

    if buf:
        paragraphs.append("\n".join(buf))

    return paragraphs


def _merge_adjacent(items: list[DeliveryItem], max_lines: int) -> list[DeliveryItem]:
    """인접한 동일 method의 multi 항목을 줄 수 한도 내에서 병합한다."""
    if len(items) <= 1:
        return items

    merged: list[DeliveryItem] = [items[0]]
    for item in items[1:]:
        prev = merged[-1]
        if prev.method == "multi" and item.method == "multi":
            combined_line_count = prev.content.count("\n") + item.content.count("\n") + 2
            if combined_line_count <= max_lines:
                merged[-1] = DeliveryItem(method="multi", content=prev.content + "\n" + item.content)
                continue
        merged.append(item)

    return merged
