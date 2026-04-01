import logging

from flask import Blueprint, request, jsonify, send_file

from api.file_delivery import save_uploaded_file, get_file_variant
from api.file_delivery.file_delivery_service import _IMAGE_EXTENSIONS, _extract_extension
from api.utils.logger import log_activity

logger = logging.getLogger(__name__)

bp = Blueprint("file_delivery", __name__)


@bp.route("/api/v1/file-delivery/upload", methods=["POST"])
@bp.route("/api/v1/cdn/upload", methods=["POST"])
def upload_file_delivery_file():
    if "file" not in request.files:
        log_activity("file_delivery_upload_rejected", reason="missing_file")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    user_id = request.form.get("user_id", "")
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
            "content_type": stored["content_type"],
            "size_bytes": stored["size_bytes"],
        }
    ), 201


@bp.route("/file-delivery/files/<file_id>")
@bp.route("/cdn/files/<file_id>")
def get_file_delivery_file(file_id: str):
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
    response = send_file(file_path, mimetype=content_type)
    response.headers["Cache-Control"] = "public, max-age=86400"

    # 비이미지 파일은 다운로드로 제공
    try:
        ext = _extract_extension(file_path.name)
    except ValueError:
        ext = ""
    if ext not in _IMAGE_EXTENSIONS:
        response.headers["Content-Disposition"] = f"attachment; filename={file_path.name}"

    return response
