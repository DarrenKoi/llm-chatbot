from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CubeIncomingMessage:
    user_id: str
    user_name: str
    channel_id: str
    message_id: str
    message: str


@dataclass(frozen=True, slots=True)
class CubeHandledMessage:
    user_id: str
    user_name: str
    channel_id: str
    message_id: str
    user_message: str
    llm_reply: str
