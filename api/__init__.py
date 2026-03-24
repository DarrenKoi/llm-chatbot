import time
import uuid

from flask import Flask
from flask import g, request
from flask import render_template

from api import config
from api.blueprint_loader import discover_blueprints
from api.conversation_service import get_recent_messages
from api.cube.payload import extract_user_id
from api.utils.logger import log_activity, setup_logging
from api.utils.scheduler import start_scheduler


def create_application() -> Flask:
    """Create and configure the Flask application."""
    setup_logging()
    if config.APP_START_SCHEDULER:
        start_scheduler()

    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def main() -> str:
        conversation = get_recent_messages(limit=50)
        return render_template("main.html", conversation=conversation)

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
