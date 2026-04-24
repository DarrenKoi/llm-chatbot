"""Dev-only helpers for composing Cube richnotification blocks."""

import re
from dataclasses import dataclass
from typing import Any

from api.cube import rich_blocks
from api.cube.payload import build_richnotification_payload

DEFAULT_HEADERS = ["Block", "Purpose", "Best practice"]
DEFAULT_ROWS = [
    ["text", "Explain the context", "Keep each sentence short"],
    ["datatable", "Compare structured values", "Use 3-5 focused columns"],
    ["container", "Adjoin blocks", "Compose blocks once, then send"],
]

_CONTROL_TOKEN_PATTERN = re.compile(r"\b(?:to|channel)=\S+", re.IGNORECASE)
_TARGET_PATTERN = re.compile(r"(?:^|\s)to=([^\s]+)", re.IGNORECASE)
_CHANNEL_PATTERN = re.compile(r"(?:^|\s)channel=([^\s]+)", re.IGNORECASE)
_SEND_WORDS = ("send", "전송", "발송")


@dataclass(frozen=True)
class DeliveryOptions:
    """Cube delivery target parsed from a dev runner message."""

    should_send: bool
    target_user_id: str
    channel_id: str


def extract_markdown_table(message: str) -> tuple[list[str], list[list[str]]] | None:
    """Extract the first markdown table from free-form text."""

    table_lines = [line.strip() for line in message.splitlines() if "|" in line]
    if len(table_lines) < 2:
        return None

    parsed_rows = [_split_table_row(line) for line in table_lines]
    separator_index = next(
        (index for index, row in enumerate(parsed_rows) if index > 0 and _is_markdown_separator_row(row)),
        -1,
    )
    if separator_index <= 0:
        return None

    headers = [cell or " " for cell in parsed_rows[separator_index - 1]]
    body_rows = [
        [cell or " " for cell in row]
        for index, row in enumerate(parsed_rows)
        if index > separator_index and row and not _is_markdown_separator_row(row)
    ]
    if not headers or not body_rows:
        return None
    return headers, body_rows


def build_text_table_blocks(message: str) -> tuple[list[rich_blocks.Block], list[str], list[list[str]]]:
    """Create text blocks and one datatable block from a dev runner message."""

    table = extract_markdown_table(message)
    if table is None:
        headers = list(DEFAULT_HEADERS)
        rows = [list(row) for row in DEFAULT_ROWS]
    else:
        headers, rows = table

    text_lines = _extract_text_lines(message)
    blocks = [
        rich_blocks.add_text("Cube richnotification block composition test"),
        rich_blocks.add_text("Text blocks and one datatable block are joined into a single content item."),
    ]
    for line in text_lines[:3]:
        blocks.append(rich_blocks.add_text(line, color="#555555"))

    blocks.append(
        rich_blocks.add_table(
            headers,
            rows,
            header_bgcolor="#E8EEF7",
            row_bgcolor="#FFFFFF",
        )
    )
    return blocks, headers, rows


def compose_content_items(
    blocks: list[rich_blocks.Block],
    *,
    callback_address: str = "",
    session_id: str = "devtools-richnotification-test",
    sequence: str = "1",
    summary: str = "devtools richnotification block test",
) -> list[dict[str, Any]]:
    """Adjoin blocks into Cube richnotification content items."""

    return [
        rich_blocks.add_container(
            *blocks,
            callback_address=callback_address,
            session_id=session_id,
            sequence=sequence,
            summary=summary,
        )
    ]


def build_payload_preview(
    *,
    content_items: list[dict[str, Any]],
    user_id: str,
    channel_id: str,
) -> dict[str, Any]:
    """Build a state-safe payload preview without exposing the bot token."""

    payload = build_richnotification_payload(
        user_id=user_id,
        channel_id=channel_id,
        content_items=content_items,
    )
    payload["richnotification"]["header"]["token"] = "<redacted>"
    return payload


def resolve_delivery_options(message: str, *, user_id: str) -> DeliveryOptions:
    """Resolve whether this devtools run should send to Cube."""

    lowered = message.lower()
    should_send = any(word in lowered for word in _SEND_WORDS)
    target_user_id = _extract_match(_TARGET_PATTERN, message)
    if not target_user_id and user_id and not _is_devtools_user_id(user_id):
        target_user_id = user_id

    channel_id = _extract_match(_CHANNEL_PATTERN, message)
    return DeliveryOptions(
        should_send=should_send,
        target_user_id=target_user_id,
        channel_id=channel_id,
    )


def _extract_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    if match is None:
        return ""
    return match.group(1).strip()


def _is_devtools_user_id(user_id: str) -> bool:
    normalized = user_id.lower()
    return normalized.startswith("dev_") or normalized.startswith("dev-")


def _extract_text_lines(message: str) -> list[str]:
    lines: list[str] = []
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped or "|" in stripped:
            continue

        cleaned = _CONTROL_TOKEN_PATTERN.sub("", stripped).strip()
        if cleaned.lower() in {"send", "preview", "미리보기", "전송", "발송"}:
            continue
        if cleaned:
            lines.append(cleaned)
    return lines


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_markdown_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(cell and set(cell) <= {":", "-", " "} and "-" in cell for cell in cells)
