import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify, send_from_directory

import config
from services.llm_service import chat
from services.conversation_service import get_history, append_message, append_messages
from services.cube_service import send_rich_notification
from services.log_service import log_request

logger = logging.getLogger(__name__)

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/v1/receive/cube", methods=["POST"])
def receive_cube():
    data = request.get_json()

    # Extract fields from Cube payload (field names are placeholders)
    user_id = data.get("user_id", "unknown")
    channel_id = data.get("channel_id", "")
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Load history and append new user message
    history = get_history(user_id)
    user_msg = {"role": "user", "content": user_message}
    append_message(user_id, user_msg)

    # Process LLM call in background thread, respond immediately
    executor.submit(_process_llm_request, user_id, channel_id, history, user_msg)

    return jsonify({"status": "accepted"}), 202


def _process_llm_request(user_id: str, channel_id: str, history: list[dict], user_msg: dict):
    """Background worker: call LLM and send reply via Cube."""
    start = time.monotonic()
    try:
        messages = [{"role": "system", "content": config.LLM_SYSTEM_PROMPT}] + history + [user_msg]

        reply_text, new_messages, metadata = chat(messages)

        append_messages(user_id, new_messages)

        image_url = _extract_image_url(new_messages)

        if channel_id:
            send_rich_notification(channel_id, reply_text, image_url=image_url)

        log_request({
            "user_id": user_id,
            "channel_id": channel_id,
            "user_message": user_msg["content"],
            "reply_text": reply_text,
            "model": config.LLM_MODEL,
            "status": "success",
            "error": None,
            "total_duration_ms": int((time.monotonic() - start) * 1000),
            "llm_calls": metadata["llm_calls"],
            "tool_executions": metadata["tool_executions"],
        })
    except Exception as e:
        logger.exception("Error processing LLM request for user %s", user_id)
        if channel_id:
            send_rich_notification(channel_id, "Sorry, something went wrong. Please try again.")

        log_request({
            "user_id": user_id,
            "channel_id": channel_id,
            "user_message": user_msg["content"],
            "reply_text": None,
            "model": config.LLM_MODEL,
            "status": "error",
            "error": str(e),
            "total_duration_ms": int((time.monotonic() - start) * 1000),
            "llm_calls": [],
            "tool_executions": [],
        })


@app.route("/static/charts/<filename>")
def serve_chart(filename):
    return send_from_directory(config.CHART_IMAGE_DIR, filename)


def _extract_image_url(messages: list[dict]) -> str | None:
    for msg in messages:
        if msg.get("role") == "tool":
            try:
                content = json.loads(msg["content"])
                if "image_url" in content:
                    return content["image_url"]
            except (json.JSONDecodeError, KeyError):
                continue
    return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.FLASK_PORT)
