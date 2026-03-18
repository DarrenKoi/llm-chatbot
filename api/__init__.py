import time
import uuid

from flask import Flask
from flask import g, request

from api.blueprint_loader import discover_blueprints
from api.utils.logger import log_activity, setup_logging
from api.utils.scheduler import start_scheduler


def _request_user_id(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    user_id = payload.get("user_id") or payload.get("user")
    if user_id:
        return str(user_id)

    rich_message = payload.get("richnotificationmessage")
    if not isinstance(rich_message, dict):
        return None

    header = rich_message.get("header")
    if not isinstance(header, dict):
        return None

    sender = header.get("from")
    if not isinstance(sender, dict):
        return None

    nested_user_id = sender.get("uniquename")
    if not nested_user_id:
        return None
    return str(nested_user_id)


def create_application() -> Flask:
    """Create and configure the Flask application."""
    setup_logging()
    start_scheduler()

    app = Flask(__name__)
    for blueprint in discover_blueprints():
        app.register_blueprint(blueprint)

    @app.before_request
    def _before_request() -> None:
        g.request_started_at = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    @app.after_request
    def _after_request(response):
        started_at = getattr(g, "request_started_at", None)
        duration_ms = int((time.monotonic() - started_at) * 1000) if started_at else None
        response.headers["X-Request-ID"] = g.request_id

        payload = request.get_json(silent=True) if request.is_json else None
        user_id = _request_user_id(payload)
        log_activity(
            "http_request",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            remote_addr=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_id=user_id,
            request_id=g.request_id,
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
