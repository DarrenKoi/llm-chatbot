"""State for the devtools richnotification block test workflow."""

from typing import Any

from api.workflows.lg_state import ChatState


class RichinotificationTestState(ChatState, total=False):
    """Keeps the latest block preview and optional Cube send status."""

    content_items: list[dict[str, Any]]
    payload_preview: dict[str, Any]
    delivery_mode: str
    delivery_target_user_id: str
    delivery_channel_id: str
    send_error: str
    table_headers: list[str]
    table_rows: list[list[str]]
