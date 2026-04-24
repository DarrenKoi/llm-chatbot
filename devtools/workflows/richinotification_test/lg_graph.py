"""Devtools LangGraph workflow for Cube richnotification block tests."""

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from api.cube.client import CubeClientError, send_richnotification_blocks

from .block_builder import (
    build_payload_preview,
    build_text_table_blocks,
    compose_content_items,
    resolve_delivery_options,
)
from .lg_state import RichinotificationTestState


def entry_node(state: RichinotificationTestState) -> dict:
    """Build text/datatable blocks, preview payload, and optionally send to Cube."""

    user_message = state.get("user_message", "")
    user_id = state.get("user_id", "")
    delivery = resolve_delivery_options(user_message, user_id=user_id)
    preview_user_id = delivery.target_user_id or user_id or "dev_preview_user"

    blocks, headers, rows = build_text_table_blocks(user_message)
    content_items = compose_content_items(blocks)
    payload_preview = build_payload_preview(
        content_items=content_items,
        user_id=preview_user_id,
        channel_id=delivery.channel_id,
    )

    delivery_mode = "preview"
    send_error = ""
    if delivery.should_send and delivery.target_user_id:
        try:
            send_richnotification_blocks(
                *blocks,
                user_id=delivery.target_user_id,
                channel_id=delivery.channel_id,
                callback_address="",
                session_id="devtools-richnotification-test",
                sequence="1",
                summary="devtools richnotification block test",
            )
            delivery_mode = "sent"
        except CubeClientError as exc:
            delivery_mode = "send_failed"
            send_error = str(exc)
    elif delivery.should_send:
        delivery_mode = "preview_missing_target"

    return {
        "messages": [
            AIMessage(
                content=_render_reply(
                    delivery_mode=delivery_mode,
                    target_user_id=delivery.target_user_id,
                    channel_id=delivery.channel_id,
                    row_count=len(rows),
                    send_error=send_error,
                )
            )
        ],
        "content_items": content_items,
        "payload_preview": payload_preview,
        "delivery_mode": delivery_mode,
        "delivery_target_user_id": delivery.target_user_id,
        "delivery_channel_id": delivery.channel_id,
        "send_error": send_error,
        "table_headers": headers,
        "table_rows": rows,
    }


def _render_reply(
    *,
    delivery_mode: str,
    target_user_id: str,
    channel_id: str,
    row_count: int,
    send_error: str,
) -> str:
    lines = [
        "This is done via devtools.",
        f"`devtools/workflows/richinotification_test` composed text blocks plus a datatable block ({row_count} rows).",
        "The State panel contains `content_items` and a token-redacted `payload_preview` for Cube inspection.",
    ]

    if delivery_mode == "sent":
        channel_text = channel_id or "DM"
        lines.append(f"Cube send completed for `{target_user_id}` via `{channel_text}`.")
    elif delivery_mode == "send_failed":
        lines.append(f"Cube send failed: {send_error}")
    elif delivery_mode == "preview_missing_target":
        lines.append("Send was requested, but no real Cube target was found. Use `to=<uniquename>` or set User ID.")
    else:
        lines.append("Preview only. Add `send to=<uniquename>` to send the same blocks to Cube.")

    return "\n".join(lines)


def build_lg_graph() -> StateGraph:
    """Return the richnotification test LangGraph builder."""

    builder = StateGraph(RichinotificationTestState)
    builder.add_node("entry", entry_node)
    builder.set_entry_point("entry")
    builder.add_edge("entry", END)
    return builder
