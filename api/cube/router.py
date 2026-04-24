from flask import Blueprint, jsonify, request

from api.cube.payload import extract_cube_request_fields as _extract_cube_request_fields
from api.cube.service import CubeWorkflowError, accept_cube_message
from api.cube.service import log_request as log_request

__all__ = [
    "bp",
    "receive_cube",
    "receive_cube_richnotification_callback",
    "_extract_cube_request_fields",
    "log_request",
]

bp = Blueprint("cube", __name__)


def _receive_cube_payload():
    try:
        result = accept_cube_message(request.get_json(silent=True))
    except CubeWorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify({"status": result.status, "message_id": result.message_id}), 200


@bp.route("/api/v1/cube/receiver", methods=["POST"])
def receive_cube():
    return _receive_cube_payload()


@bp.route("/api/v1/cube/richnotification/callback", methods=["POST"])
def receive_cube_richnotification_callback():
    return _receive_cube_payload()
