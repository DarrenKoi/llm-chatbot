import json

from flask import Flask, request, jsonify, send_from_directory

import config
from services.llm_service import chat
from services.conversation_service import get_history, append_message, append_messages
from services.cube_service import send_rich_notification

app = Flask(__name__)


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

    # Build full message list: system + history + new message
    messages = [{"role": "system", "content": config.LLM_SYSTEM_PROMPT}] + history + [user_msg]

    # Call LLM (with tool-use loop)
    reply_text, new_messages = chat(messages)

    # Persist assistant/tool messages to history
    append_messages(user_id, new_messages)

    # Check if any tool produced an image URL
    image_url = _extract_image_url(new_messages)

    # Send response back via Cube (stub)
    if channel_id:
        send_rich_notification(channel_id, reply_text, image_url=image_url)

    return jsonify({"reply": reply_text, "image_url": image_url})


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
