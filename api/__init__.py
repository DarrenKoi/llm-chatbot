import time
import uuid
from pathlib import Path

from flask import Flask, g, render_template, request

from api import config as config
from api.blueprint_loader import discover_blueprints
from api.conversation_service import get_recent_messages
from api.cube.payload import extract_user_id
from api.monitoring_service import get_monitoring_snapshot
from api.scheduled_tasks.inspection import get_scheduled_tasks_snapshot
from api.utils.logger import log_activity, setup_logging
from api.workflows.graph_visualizer import build_workflow_html, list_workflow_ids


def create_application() -> Flask:
    """Flask 애플리케이션을 생성하고 설정한다.

    로깅 초기화 → 라우트 등록 → 블루프린트 자동 탐색 순으로 앱을 구성한다.
    """
    setup_logging()

    template_directory = Path(__file__).resolve().parent / "html_templates"
    app = Flask(__name__, template_folder=str(template_directory))

    @app.route("/", methods=["GET"])
    def landing_page() -> str:
        """서버 상태 확인용 랜딩 페이지를 반환한다."""
        return render_template("landing.html")

    @app.route("/conversation", methods=["GET"])
    def conversation_page() -> str:
        """최근 대화 이력 50건을 HTML로 렌더링해서 반환한다."""
        conversation = get_recent_messages(limit=50)
        return render_template("conversation.html", conversation=conversation)

    @app.route("/monitor", methods=["GET"])
    def monitor() -> str:
        """MongoDB·Redis·데몬 등 백엔드 서비스 상태를 대시보드로 반환한다."""
        snapshot = get_monitoring_snapshot()
        return render_template("monitor.html", snapshot=snapshot)

    @app.route("/scheduled_tasks", methods=["GET"])
    def scheduled_tasks() -> str:
        """APScheduler에 등록된 태스크 목록과 실행 현황을 반환한다."""
        snapshot = get_scheduled_tasks_snapshot()
        return render_template("scheduled_tasks.html", snapshot=snapshot)

    @app.route("/workflows", methods=["GET"])
    def workflow_list() -> str:
        """등록된 워크플로 목록을 링크로 나열한다."""
        ids = list_workflow_ids()
        links = "".join(f'<li><a href="/workflows/{wid}">{wid}</a></li>' for wid in ids)
        return f"<h1>Workflows</h1><ul>{links}</ul>"

    @app.route("/workflows/<workflow_id>", methods=["GET"])
    def workflow_graph(workflow_id: str) -> str:
        """특정 워크플로의 LangGraph 노드 구조를 인터랙티브 HTML로 반환한다."""
        return build_workflow_html(workflow_id)

    for blueprint in discover_blueprints():
        app.register_blueprint(blueprint)

    @app.before_request
    def _before_request() -> None:
        """요청마다 시작 시각과 고유 request_id를 Flask g에 저장한다."""
        g.request_started_at = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.request_json = request.get_json(silent=True) if request.is_json else None

    @app.after_request
    def _after_request(response):
        """요청 처리 후 소요 시간·상태 코드 등을 activity log에 기록한다."""
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
        """요청 처리 중 예외가 발생한 경우 ERROR 레벨로 activity log에 기록한다."""
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
