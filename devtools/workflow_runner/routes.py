"""Dev workflow runner API 엔드포인트."""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from devtools.workflow_runner.dev_orchestrator import (
    get_dev_state,
    handle_dev_message,
    list_dev_workflow_ids,
    load_dev_workflows,
    reset_dev_state,
)
from devtools.workflow_runner.identity import get_default_dev_user_id

log = logging.getLogger(__name__)

_pkg_dir = Path(__file__).resolve().parent
dev_bp = Blueprint(
    "dev_runner",
    __name__,
    static_folder=str(_pkg_dir / "static"),
    static_url_path="/static",
)


@dev_bp.route("/")
def index():
    """Dev runner UI 페이지를 서빙한다."""

    return render_template("runner.html", default_user_id=get_default_dev_user_id())


@dev_bp.route("/api/workflows")
def api_workflows():
    """등록된 dev workflow 목록을 반환한다."""

    load_dev_workflows()
    return jsonify({"workflows": list_dev_workflow_ids()})


@dev_bp.route("/api/send", methods=["POST"])
def api_send():
    """메시지를 전송하고 reply + trace + state를 반환한다."""

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "요청 본문은 JSON 객체여야 합니다."}), 400

    workflow_id = str(body.get("workflow_id", "")).strip()
    message = str(body.get("message", "")).strip()
    default_user_id = get_default_dev_user_id()
    user_id = str(body.get("user_id", default_user_id)).strip() or default_user_id

    if not workflow_id:
        return jsonify({"error": "workflow_id가 필요합니다."}), 400
    if not message:
        return jsonify({"error": "message가 필요합니다."}), 400

    try:
        result = handle_dev_message(
            workflow_id=workflow_id,
            user_message=message,
            user_id=user_id,
        )
        return jsonify(result)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        log.exception("dev workflow 실행 중 오류 발생")
        return jsonify({"error": str(exc)}), 500


@dev_bp.route("/api/state")
def api_state():
    """현재 workflow state를 조회한다."""

    default_user_id = get_default_dev_user_id()
    user_id = str(request.args.get("user_id", default_user_id)).strip() or default_user_id
    state = get_dev_state(user_id=user_id)
    if state is None:
        return jsonify({"state": None})
    return jsonify({"state": state})


@dev_bp.route("/api/state", methods=["DELETE"])
def api_state_reset():
    """workflow state를 초기화한다."""

    default_user_id = get_default_dev_user_id()
    user_id = str(request.args.get("user_id", default_user_id)).strip() or default_user_id
    reset_dev_state(user_id=user_id)
    return jsonify({"ok": True})


@dev_bp.route("/api/reload", methods=["POST"])
def api_reload():
    """dev workflow 목록을 강제 새로고침한다."""

    load_dev_workflows(force_reload=True)
    return jsonify({"workflows": list_dev_workflow_ids()})
