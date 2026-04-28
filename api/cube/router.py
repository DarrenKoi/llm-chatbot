import json
import logging

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

logger = logging.getLogger(__name__)

bp = Blueprint("cube", __name__)


def _log_inbound(endpoint: str, payload: object) -> None:
    """라우트 진입 시 원본 페이로드를 그대로 기록한다.

    파싱 이전 단계라 Cube가 실제로 POST했는지 여부를 가장 먼저 확인할 수 있다.
    """
    try:
        body = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        body = repr(payload)
    logger.info("cube_inbound endpoint=%s payload=%s", endpoint, body)


def _receive_cube_payload(endpoint: str):
    payload = request.get_json(silent=True)
    _log_inbound(endpoint, payload)
    try:
        result = accept_cube_message(payload)
    except CubeWorkflowError as exc:
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify({"status": result.status, "message_id": result.message_id}), 200


@bp.route("/api/v1/cube/receiver", methods=["POST"])
def receive_cube():
    return _receive_cube_payload("receiver")


@bp.route("/api/v1/cube/richnotification/callback", methods=["POST"])
def receive_cube_richnotification_callback():
    return _receive_cube_payload("richnotification_callback")
