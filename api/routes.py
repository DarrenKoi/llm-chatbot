import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, request, jsonify, send_from_directory, send_file

from api import config
from api.services.llm_service import chat
from api.services.conversation_service import get_history, append_message, append_messages
from api.services.cdn import save_uploaded_image, get_image_variant_file
from api.services.cube_service import send_rich_notification
from api.services.log_service import log_request

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__)
executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)


@chatbot_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@chatbot_bp.route("/api/v1/cdn/upload", methods=["POST"])
def upload_cdn_image():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    try:
        stored = save_uploaded_image(file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("CDN upload failed")
        return jsonify({"error": "Failed to upload image"}), 500

    return jsonify(
        {
            "image_id": stored["image_id"],
            "image_url": stored["image_url"],
            "content_type": stored["content_type"],
            "size_bytes": stored["size_bytes"],
        }
    ), 201


@chatbot_bp.route("/cdn/images/<image_id>")
def get_cdn_image(image_id: str):
    width_arg = request.args.get("w")
    height_arg = request.args.get("h")
    thumbnail_arg = request.args.get("thumbnail", "").lower()

    try:
        width = int(width_arg) if width_arg else None
        height = int(height_arg) if height_arg else None
    except ValueError:
        return jsonify({"error": "w and h must be integers"}), 400

    thumbnail = thumbnail_arg in {"1", "true", "yes", "y"}

    try:
        image = get_image_variant_file(image_id, width=width, height=height, thumbnail=thumbnail)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    if image is None:
        return jsonify({"error": "Image not found"}), 404

    file_path, content_type = image
    response = send_file(file_path, mimetype=content_type)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@chatbot_bp.route("/api/v1/receive/cube", methods=["POST"])
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


@chatbot_bp.route("/static/charts/<filename>")
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
