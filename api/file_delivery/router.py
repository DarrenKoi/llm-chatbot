import logging

from flask import Blueprint, jsonify, render_template, request, send_file

from api.file_delivery import (
    get_file_metadata,
    get_file_variant,
    is_image_file,
    list_files_for_user,
    save_uploaded_file,
)
from api.logging_service import log_activity

_FILE_LIST_FIELDS = (
    "file_id",
    "file_url",
    "original_filename",
    "title",
    "content_type",
    "size_bytes",
    "created_at",
    "source",
)

logger = logging.getLogger(__name__)

bp = Blueprint("file_delivery", __name__)


def _resolve_request_user_id() -> str:
    return request.cookies.get("LASTUSER", "").strip()


@bp.route("/file-delivery", methods=["GET"])
@bp.route("/file_delivery", methods=["GET"])
def file_delivery_page():
    user_id = request.cookies.get("LASTUSER", "").strip()
    recent_files = list_files_for_user(user_id=user_id, limit=20) if user_id else []
    return render_template("file_delivery.html", user_id=user_id, recent_files=recent_files)


@bp.route("/api/v1/file-delivery/upload", methods=["POST"])
@bp.route("/api/v1/file_delivery/upload", methods=["POST"])
@bp.route("/api/v1/cdn/upload", methods=["POST"])
def upload_file_delivery_file():
    if "file" not in request.files:
        log_activity("file_delivery_upload_rejected", reason="missing_file")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    user_id = _resolve_request_user_id()
    if not user_id:
        log_activity("file_delivery_upload_rejected", reason="missing_user")
        return jsonify({"error": "Unable to resolve user from session"}), 400
    title = request.form.get("title", "")
    try:
        stored = save_uploaded_file(file, user_id=user_id, title=title)
    except ValueError as e:
        log_activity("file_delivery_upload_rejected", reason=str(e))
        return jsonify({"error": str(e)}), 400
    except Exception:
        logger.exception("File delivery upload failed")
        log_activity("file_delivery_upload_failed", level="ERROR")
        return jsonify({"error": "Failed to upload file"}), 500

    log_activity(
        "file_delivery_upload_success",
        file_id=stored["file_id"],
        stored_filename=stored["stored_filename"],
        content_type=stored["content_type"],
        size_bytes=stored["size_bytes"],
    )
    return jsonify(
        {
            "file_id": stored["file_id"],
            "file_url": stored["file_url"],
            "stored_filename": stored["stored_filename"],
            "user_id": stored["user_id"],
            "content_type": stored["content_type"],
            "size_bytes": stored["size_bytes"],
        }
    ), 201


@bp.route("/api/v1/file-delivery/files", methods=["GET"])
@bp.route("/api/v1/file_delivery/files", methods=["GET"])
def list_user_delivery_files():
    user_id = _resolve_request_user_id()
    if not user_id:
        return jsonify({"error": "Unable to resolve user from session"}), 400

    try:
        raw_limit = request.args.get("limit", "20")
        limit = max(1, min(int(raw_limit), 100))
    except ValueError:
        limit = 20

    try:
        files = list_files_for_user(user_id=user_id, limit=limit)
    except Exception:
        logger.exception("File delivery list failed")
        return jsonify({"error": "Failed to load file list"}), 500
    trimmed = [{k: f[k] for k in _FILE_LIST_FIELDS if k in f} for f in files]
    return jsonify({"files": trimmed, "total": len(trimmed)})


@bp.route("/file-delivery/files/<file_id>")
@bp.route("/file-delivery-files/<file_id>")
@bp.route("/file_delivery/files/<file_id>")
@bp.route("/cdn/files/<file_id>")
def get_file_delivery_file(file_id: str):
    # TODO: This download route is currently public by file_id. Revisit whether
    # listing APIs and chat responses should expose URLs without an owner check.
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
        result = get_file_variant(file_id, width=width, height=height, thumbnail=thumbnail)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    if result is None:
        return jsonify({"error": "File not found"}), 404

    file_path, content_type = result
    metadata = get_file_metadata(file_id) or {}

    if not is_image_file(file_path.name):
        response = send_file(
            file_path,
            mimetype=content_type,
            as_attachment=True,
            download_name=metadata.get("original_filename") or file_path.name,
        )
    else:
        response = send_file(file_path, mimetype=content_type)

    response.headers["Cache-Control"] = "public, max-age=86400"

    return response
