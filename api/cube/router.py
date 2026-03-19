from flask import Blueprint, jsonify, request

from api.cube.payload import extract_cube_request_fields as _extract_cube_request_fields
from api.cube.service import CubeWorkflowError, accept_cube_message, log_request

bp = Blueprint("cube", __name__)


@bp.route("/api/v1/cube/receiver", methods=["POST"])
def receive_cube():
    try:
        result = accept_cube_message(request.get_json(silent=True))
    except CubeWorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify({"status": result.status, "message_id": result.message_id}), 200
