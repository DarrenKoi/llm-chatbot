import time
import uuid
from pathlib import Path

from flask import Flask
from flask import g, request
from flask import render_template

from api import config
from api.blueprint_loader import discover_blueprints
from api.conversation_service import get_recent_messages
from api.cube.payload import extract_user_id
from api.monitoring_service import get_monitoring_snapshot
from api.scheduled_tasks.inspection import get_scheduled_tasks_snapshot
from api.utils.logger import log_activity, setup_logging
from api.workflows.graph_visualizer import build_workflow_html, list_workflow_ids


def create_application() -> Flask:
    """Create and configure the Flask application."""
    setup_logging()

    template_directory = Path(__file__).resolve().parent / "html_templates"
    app = Flask(__name__, template_folder=str(template_directory))

    @app.route("/", methods=["GET"])
    def main() -> str:
        conversation = get_recent_messages(limit=50)
        return render_template("main.html", conversation=conversation)

    @app.route("/monitor", methods=["GET"])
    def monitor() -> str:
        snapshot = get_monitoring_snapshot()
        return render_template("monitor.html", snapshot=snapshot)

    @app.route("/scheduled_tasks", methods=["GET"])
    def scheduled_tasks() -> str:
        snapshot = get_scheduled_tasks_snapshot()
        return render_template("scheduled_tasks.html", snapshot=snapshot)

    @app.route("/workflows", methods=["GET"])
    def workflow_list() -> str:
        ids = list_workflow_ids()
        links = "".join(f'<li><a href="/workflows/{wid}">{wid}</a></li>' for wid in ids)
        return f"<h1>Workflows</h1><ul>{links}</ul>"

    @app.route("/workflows/<workflow_id>", methods=["GET"])
    def workflow_graph(workflow_id: str) -> str:
        return build_workflow_html(workflow_id)

    for blueprint in discover_blueprints():
        app.register_blueprint(blueprint)

    @app.before_request
    def _before_request() -> None:
        g.request_started_at = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.request_json = request.get_json(silent=True) if request.is_json else None

    @app.after_request
    def _after_request(response):
        started_at = getattr(g, "request_started_at", None)
        duration_ms = int((time.monotonic() - started_at) * 1000) if started_at else None
        request_id = getattr(g, "request_id", None) or uuid.uuid4().hex
        response.headers["X-Request-ID"] = request_id

        user_id = extract_user_id(getattr(g, "request_json", None))
        log_activity(
            "http_request",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            remote_addr=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_id=user_id,
            request_id=request_id,
        )
        return response

    @app.teardown_request
    def _teardown_request(error: BaseException | None) -> None:
        if error is None:
            return
        log_activity(
            "http_request_error",
            level="ERROR",
            path=request.path,
            method=request.method,
            error=str(error),
            request_id=getattr(g, "request_id", None),
        )

    return app
